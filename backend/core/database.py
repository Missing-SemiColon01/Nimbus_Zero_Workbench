import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from backend.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_mongo_client: AsyncIOMotorClient | None = None
_mongo_db: AsyncIOMotorDatabase | None = None


async def init_mongo(settings: Settings | None = None) -> AsyncIOMotorDatabase | None:
    """Initialize MongoDB connection pool using Motor."""
    global _mongo_client, _mongo_db
    if settings is None:
        settings = get_settings()

    if not settings.mongodb_uri:
        logger.warning("MONGODB_URI not configured. Authentication will operate in standalone local mode.")
        return None

    try:
        _mongo_client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
        )
        _mongo_db = _mongo_client[settings.mongodb_db_name]

        # Test connection with a ping command
        await _mongo_db.command("ping")
        logger.info(f"Connected to MongoDB database: {settings.mongodb_db_name}")

        # Ensure unique index on users.email
        await _mongo_db.users.create_index("email", unique=True)
        return _mongo_db
    except Exception as exc:
        logger.error(f"Failed to connect to MongoDB: {exc}")
        # Retain client reference for reconnect attempts or leave as None
        _mongo_db = None
        return None


async def close_mongo() -> None:
    """Close MongoDB connection pool."""
    global _mongo_client, _mongo_db
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("Closed MongoDB connection pool.")


def get_database() -> AsyncIOMotorDatabase | None:
    """Get the active Motor database instance, or None if not connected."""
    return _mongo_db


def is_mongo_connected() -> bool:
    """Check if MongoDB database is available."""
    return _mongo_db is not None

