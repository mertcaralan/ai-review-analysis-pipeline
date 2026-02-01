from fastapi import Depends
from api.config import Settings, get_settings
from api.storage.in_memory import InMemoryStore, get_store


def get_config() -> Settings:
    """Dependency for settings."""
    return get_settings()


def get_storage() -> InMemoryStore:
    """Dependency for in-memory store."""
    return get_store()
