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

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "db_ops_group")
TOPIC = os.getenv("KAFKA_TOPIC", "user.events")

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

async def handle_message(msg_value: bytes):
    global db_manager
    try:
        data = json.loads(msg_value.decode())
        logger.info("Handling event: %s", data)
        event = data.get("event")
        # Ensure DB connected
        if db_manager is None:
            logger.warning("Database manager not initialized; attempting to connect")
            db_manager = DatabaseManager()
            try:
                db_manager.connect()
            except Exception as e:
                logger.exception("DB connect failed while handling event: %s", e)
                return

        if event == "user.registered":
            user_id = data.get("user_id")
            email = data.get("email")
            # Persist user lightweight data into Redis (fast-access store)
            redis_client = getattr(db_manager, "redis_client", None)
            if redis_client:
                try:
                    key = f"user:{user_id}"
                    payload = {"user_id": user_id, "email": email}
                    # store as JSON string
                    redis_client.set(key, json.dumps(payload))
                    logger.info("Stored user in Redis key=%s", key)
                except Exception:
                    logger.exception("Failed to write user to Redis")
            else:
                logger.warning("No redis client available; skipping Redis write for user %s", user_id)

            # Optionally insert an audit/event row in Postgres for traceability
            try:
                db_manager.cursor.execute(
                    "INSERT INTO events (topic, event_type, payload) VALUES (%s, %s, %s)",
                    (TOPIC, event, json.dumps(data))
                )
                logger.info("Logged user.registered event to Postgres events table for user_id=%s", user_id)
            except Exception:
                logger.exception("Failed to log event to Postgres for user.registered")
        else:
            # For all other events, store them in Postgres events table
            try:
                db_manager.cursor.execute(
                    "INSERT INTO events (topic, event_type, payload) VALUES (%s, %s, %s)",
                    (TOPIC, event, json.dumps(data))
                )
                logger.info("Stored event type %s in Postgres events table", event)
            except Exception:
                logger.exception("Failed to store event in Postgres")
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

    # Ensure events table exists for storing non-user events
    try:
        ensure_events_table()
    except Exception:
        logger.exception("Could not ensure events table")

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info(
        "Kafka consumer started (bootstrap=%s, topic=%s, group=%s)",
        KAFKA_BOOTSTRAP,
        TOPIC,
        CONSUMER_GROUP,
    )
    try:
        async for msg in consumer:
            await handle_message(msg.value)
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
