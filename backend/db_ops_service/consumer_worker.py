import os
import asyncio
import json
import logging
from aiokafka import AIOKafkaConsumer
from database.connection import DatabaseManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "db_ops_group")
TOPIC = os.getenv("KAFKA_TOPIC", "user.events")

async def handle_message(msg_value: bytes):
    try:
        data = json.loads(msg_value.decode())
        logger.info("Handling event: %s", data)
        # Example: react to user.registered events
        event = data.get("event")
        if event == "user.registered":
            user_id = data.get("user_id")
            email = data.get("email")
            # Connect to DB and perform tasks (e.g., analytics, welcome email enqueue)
            db = DatabaseManager()
            # Ensure DB is connected (DatabaseManager.connect uses env vars)
            if db.cursor is None:
                try:
                    db.connect()
                except Exception as e:
                    logger.exception("DB connect failed while handling event: %s", e)
                    return
            logger.info("Consumed user.registered for user_id=%s email=%s", user_id, email)
            # TODO: implement actual handling (e.g., write audit row, call external service)
        else:
            logger.info("Unhandled event type: %s", event)
    except Exception:
        logger.exception("Failed to process message")

async def consumer_loop():
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("Kafka consumer started (bootstrap=%s, topic=%s, group=%s)", KAFKA_BOOTSTRAP, TOPIC, CONSUMER_GROUP)
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
