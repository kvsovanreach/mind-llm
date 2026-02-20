"""
Redis utilities for state management.
"""
import redis
import logging
from typing import Optional, List, Dict, Any
from config import REDIS_HOST, REDIS_PORT

logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    """
    Get a Redis client connection.

    Returns:
        Redis client object
    """
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_free_port(redis_client: redis.Redis, start_port: int = 8100) -> int:
    """
    Find an available port for a new model container.

    Args:
        redis_client: Redis connection
        start_port: Starting port number

    Returns:
        Available port number
    """
    used_ports = set()
    for key in redis_client.keys("model:*"):
        model_data = redis_client.hgetall(key)
        if model_data.get("port"):
            used_ports.add(int(model_data["port"]))

    port = start_port
    while port in used_ports:
        port += 1
    return port


def save_model_state(
    redis_client: redis.Redis,
    abbr: str,
    data: Dict[str, Any]
) -> None:
    """
    Save model state to Redis.

    Args:
        redis_client: Redis connection
        abbr: Model abbreviation
        data: Model data to save
    """
    # Convert all values to strings for Redis
    string_data = {k: str(v) if v is not None else "" for k, v in data.items()}
    redis_client.hset(f"model:{abbr}", mapping=string_data)


def get_model_state(
    redis_client: redis.Redis,
    abbr: str
) -> Optional[Dict[str, Any]]:
    """
    Get model state from Redis.

    Args:
        redis_client: Redis connection
        abbr: Model abbreviation

    Returns:
        Model state dictionary or None if not found
    """
    if redis_client.exists(f"model:{abbr}"):
        return redis_client.hgetall(f"model:{abbr}")
    return None


def update_model_status(
    redis_client: redis.Redis,
    abbr: str,
    status: str,
    progress: Optional[int] = None,
    progress_message: Optional[str] = None
) -> None:
    """
    Update model deployment status.

    Args:
        redis_client: Redis connection
        abbr: Model abbreviation
        status: New status
        progress: Optional progress percentage
        progress_message: Optional progress message
    """
    updates = {"status": status}
    if progress is not None:
        updates["progress"] = str(progress)
    if progress_message is not None:
        updates["progress_message"] = progress_message

    redis_client.hset(f"model:{abbr}", mapping=updates)


def delete_model_state(
    redis_client: redis.Redis,
    abbr: str
) -> bool:
    """
    Delete model state from Redis.

    Args:
        redis_client: Redis connection
        abbr: Model abbreviation

    Returns:
        True if deleted, False if not found
    """
    if redis_client.exists(f"model:{abbr}"):
        redis_client.delete(f"model:{abbr}")
        # Also delete GPU assignment
        redis_client.delete(f"gpu_assignment:{abbr}")
        return True
    return False


def list_models(
    redis_client: redis.Redis,
    status_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all models with optional status filter.

    Args:
        redis_client: Redis connection
        status_filter: Optional status to filter by

    Returns:
        List of model state dictionaries
    """
    models = []
    for key in redis_client.keys("model:*"):
        model_data = redis_client.hgetall(key)
        if status_filter is None or model_data.get("status") == status_filter:
            models.append(model_data)
    return models


# API Key Management
def create_api_key(
    redis_client: redis.Redis,
    name: str
) -> str:
    """
    Create a new API key.

    Args:
        redis_client: Redis connection
        name: Name/description for the API key

    Returns:
        Generated API key
    """
    import uuid
    api_key = f"sk-{uuid.uuid4().hex}"
    redis_client.hset(f"api_key:{api_key}", mapping={
        "name": name,
        "created_at": str(uuid.uuid4().int)  # Timestamp-like
    })
    return api_key


def verify_api_key(
    redis_client: redis.Redis,
    api_key: str
) -> bool:
    """
    Verify if an API key is valid.

    Args:
        redis_client: Redis connection
        api_key: API key to verify

    Returns:
        True if valid, False otherwise
    """
    return redis_client.exists(f"api_key:{api_key}")


def list_api_keys(
    redis_client: redis.Redis
) -> List[Dict[str, str]]:
    """
    List all API keys.

    Args:
        redis_client: Redis connection

    Returns:
        List of API key information
    """
    keys = []
    for key in redis_client.keys("api_key:*"):
        api_key = key.split(":", 1)[1]
        key_data = redis_client.hgetall(key)
        keys.append({
            "key": api_key,  # Return full key - frontend will handle masking
            "name": key_data.get("name", ""),
            "created_at": key_data.get("created_at", "")
        })
    return keys


def delete_api_key(
    redis_client: redis.Redis,
    api_key: str
) -> bool:
    """
    Delete an API key.

    Args:
        redis_client: Redis connection
        api_key: API key to delete

    Returns:
        True if deleted, False if not found
    """
    if redis_client.exists(f"api_key:{api_key}"):
        redis_client.delete(f"api_key:{api_key}")
        return True
    return False