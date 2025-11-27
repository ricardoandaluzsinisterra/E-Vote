import os
import sys
import asyncio
import json
import logging
import time

# Ensure project root is on PYTHONPATH so imports like `database` resolve when running this module directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aiokafka import AIOKafkaConsumer
from database.connection import DatabaseManager
from database.operations import get_user_by_email_as_user
from models.User import User
import psycopg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "db_ops_group")
POSTGRES_TOPIC = os.getenv("KAFKA_POSTGRES_TOPIC", "user.postgres.ops")
REDIS_TOPIC = os.getenv("KAFKA_REDIS_TOPIC", "user.redis.ops")

# Singleton DatabaseManager instance (initialized in consumer_loop)
db_manager: DatabaseManager | None = None

def ensure_events_table():
    """
    Create a simple events table for storing non-user events in Postgres.
    """
    global db_manager
    try:
        db_manager.cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                topic VARCHAR(255),
                event_type VARCHAR(255),
                payload JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Ensured events table exists")
    except Exception as e:
        logger.exception("Failed to ensure events table: %s", e)

def ensure_users_table():
    """
    Ensure canonical users table exists in Postgres.
    """
    global db_manager
    try:
        db_manager.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                verification_token VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Ensured users table exists")
    except Exception as e:
        logger.exception("Failed to ensure users table: %s", e)

async def handle_postgres_event(data: dict):
    """
    Handle messages sent to the Postgres ops topic (user.create, user.verify, etc).
    """
    global db_manager
    event = data.get("event") or data.get("op")
    resource = data.get("resource")
    payload = data.get("payload", {})

    # Audit every message into events table
    try:
        db_manager.cursor.execute(
            "INSERT INTO events (topic, event_type, payload) VALUES (%s, %s, %s)",
            (POSTGRES_TOPIC, event, json.dumps(data))
        )
    except Exception:
        logger.exception("Failed to log event to Postgres events table")

    # Only handle user resource here
    if resource != "user":
        logger.debug("Postgres handler ignoring non-user resource: %s", resource)
        return

    if event in ("create", "user.registered"):
        email = payload.get("email")
        password_hash = payload.get("password_hash")
        verification_token = payload.get("verification_token")
        # Insert canonical user row if not exists
        try:
            insert_sql = """
                INSERT INTO users (email, password_hash, is_verified, verification_token)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """
            db_manager.cursor.execute(insert_sql, (email, password_hash, False, verification_token))
            new_id = db_manager.cursor.fetchone()[0]
            logger.info("Inserted user into Postgres id=%s email=%s", new_id, email)
        except psycopg.IntegrityError:
            # user already exists; attempt to fetch existing id
            logger.info("User already exists in Postgres: %s", email)
            try:
                db_manager.cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
                row = db_manager.cursor.fetchone()
                logger.info("Existing user id=%s", row[0] if row else None)
            except Exception:
                logger.exception("Failed to fetch existing user id after IntegrityError")
        except Exception:
            logger.exception("Failed to insert user into Postgres")

    elif event in ("verify", "user.verified"):
        verification_token = payload.get("verification_token") or payload.get("token")
        if not verification_token:
            logger.warning("Verify event missing verification_token")
            return
        try:
            update_sql = "UPDATE users SET is_verified = true WHERE verification_token = %s;"
            db_manager.cursor.execute(update_sql, (verification_token,))
            if db_manager.cursor.rowcount == 0:
                logger.warning("Verification token not found in Postgres: %s", verification_token)
            else:
                logger.info("Marked user verified for token=%s", verification_token)
        except Exception:
            logger.exception("Failed to update user verification in Postgres")

    else:
        logger.debug("Unhandled postgres event type: %s", event)

async def handle_redis_event(data: dict):
    """
    Handle messages sent to Redis ops topic. These are intended for cache updates/invalidations.
    """
    global db_manager
    event = data.get("event") or data.get("op")
    resource = data.get("resource")
    payload = data.get("payload", {})

    redis_client = getattr(db_manager, "redis_client", None)
    if resource != "user":
        logger.debug("Redis handler ignoring non-user resource: %s", resource)
        return

    if redis_client is None:
        logger.warning("No redis client available; skipping redis event handling")
        return

    if event in ("create", "user.registered"):
        email = payload.get("email")
        user_id = payload.get("user_id")
        verification_token = payload.get("verification_token")
        is_verified = payload.get("is_verified", False)
        key = f"user:email:{email}"
        try:
            redis_client.set(key, json.dumps({
                "user_id": user_id,
                "email": email,
                "password_hash": payload.get("password_hash"),
                "is_verified": is_verified,
                "verification_token": verification_token,
                "created_at": payload.get("created_at")
            }), ex=3600)
            logger.info("Cached user in Redis key=%s", key)
        except Exception:
            logger.exception("Failed to cache user in Redis")

    elif event in ("verify", "user.verified"):
        email = payload.get("email")
        # Invalidate or update cache entry
        try:
            if email:
                key = f"user:email:{email}"
                cached = redis_client.get(key)
                if cached:
                    try:
                        data_obj = json.loads(cached)
                        data_obj["is_verified"] = True
                        redis_client.set(key, json.dumps(data_obj), ex=3600)
                        logger.info("Updated cached user is_verified in Redis for email=%s", email)
                    except Exception:
                        # If parse fails, delete cache to force refresh
                        redis_client.delete(key)
                        logger.info("Deleted invalid cache for email=%s", email)
                else:
                    logger.info("No cache found to update for email=%s", email)
            else:
                # If email not provided, no-op or consider scanning by token (avoid expensive ops)
                logger.debug("Verify event did not include email; skipping cache update")
        except Exception:
            logger.exception("Failed to update/invalidate cache for verification")

    else:
        logger.debug("Unhandled redis event type: %s", event)

async def handle_message(msg_value: bytes):
    global db_manager
    try:
        data = json.loads(msg_value.decode())
        logger.info("Handling event: %s", data)
        op = data.get("op") or data.get("event")
        topic_hint = data.get("meta", {}).get("topic")  # optional
        # Ensure DB connected
        if db_manager is None:
            logger.warning("Database manager not initialized; attempting to connect")
            db_manager = DatabaseManager()
            try:
                db_manager.connect()
            except Exception as e:
                logger.exception("DB connect failed while handling event: %s", e)
                return

        # Process based on where the message came from (topics subscribed below)
        # Decide whether to treat as Postgres op or Redis op by presence of op/resource and the consumer's assigned topic
        # The outer consumer loop will call handle_message for messages from all topics; include topic in envelope if needed.

        # Determine handling based on op/resource/topic fields
        if data.get("meta", {}).get("target") == "redis" or data.get("meta", {}).get("topic") == REDIS_TOPIC:
            await handle_redis_event(data)
        else:
            # default to Postgres handling
            await handle_postgres_event(data)

    except Exception:
        logger.exception("Failed to process message")

async def consumer_loop():
    global db_manager
    # Initialize DB manager and connections first so Redis/Postgres are ready
    db_manager = DatabaseManager()
    # Retry connect with backoff to improve robustness during service startup
    for attempt in range(6):
        try:
            db_manager.connect()
            logger.info("Connected to Postgres/Redis via DatabaseManager")
            break
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("Database connect attempt %s failed: %s. Retrying in %s seconds", attempt + 1, e, wait)
            time.sleep(wait)
    else:
        logger.error("Unable to connect to Postgres after retries; consumer will still start but DB writes will fail")

    # Ensure events and users tables exist for storing canonical data/audit
    try:
        ensure_events_table()
        ensure_users_table()
    except Exception:
        logger.exception("Could not ensure required tables")

    topics = [t for t in (os.getenv("KAFKA_POSTGRES_TOPIC", POSTGRES_TOPIC), os.getenv("KAFKA_REDIS_TOPIC", REDIS_TOPIC)) if t]
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info(
        "Kafka consumer started (bootstrap=%s, topics=%s, group=%s)",
        KAFKA_BOOTSTRAP,
        topics,
        CONSUMER_GROUP,
    )
    try:
        async for msg in consumer:
            # msg.topic is available to decide routing
            try:
                payload = msg.value
                # include topic meta so handlers can choose path if needed
                # attach topic into envelope if not present
                try:
                    parsed = json.loads(payload.decode())
                    if isinstance(parsed, dict):
                        parsed.setdefault("meta", {})
                        parsed["meta"].setdefault("topic", msg.topic)
                        await handle_message(json.dumps(parsed).encode())
                    else:
                        await handle_message(payload)
                except Exception:
                    await handle_message(payload)
            except Exception:
                logger.exception("Error handling Kafka message")
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped")

def main():
    try:
        asyncio.run(consumer_loop())
    except KeyboardInterrupt:
        logger.info("Consumer interrupted and exiting")

if __name__ == "__main__":
    main()
