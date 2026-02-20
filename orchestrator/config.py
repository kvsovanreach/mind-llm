"""
Configuration management for the orchestrator service.
Handles environment variables, paths, and models.json loading.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Environment Variables
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
HF_TOKEN = os.getenv("HF_TOKEN", "")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-this-in-production")
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", 24))

# Path Configuration
HF_CACHE_DIR = os.getenv("HF_CACHE_DIR", "/root/.cache/huggingface/hub")
HOST_CACHE_DIR = os.getenv("HOST_CACHE_DIR", "~/.cache")
MODELS_DIR = os.getenv("MODELS_DIR", "/models")
HOST_MODELS_DIR = os.getenv("HOST_MODELS_DIR", "./models")

# Models configuration file
MODELS_CONFIG_PATH = "/app/models.json"
# Fallback to environment variable or local path
if not os.path.exists(MODELS_CONFIG_PATH):
    MODELS_CONFIG_PATH = os.getenv("MODELS_CONFIG_PATH", "./frontend/src/models.json")

# Network configuration
NETWORK_NAME = "mind_llm-network"
MODEL_CONTAINER_PREFIX = "MIND_MODEL_"
NGINX_CONTAINER = "MIND_API_GATEWAY"
REDIS_CONTAINER = "MIND_REDIS_STORE"

# Port configuration
ORCHESTRATOR_PORT = 8001
MODEL_PORT_START = 8100
VLLM_DEFAULT_PORT = 8000

# GPU Configuration
DEFAULT_GPU_MEMORY_UTILIZATION = 0.9
DEFAULT_MAX_MODEL_LEN = 4096
DEFAULT_MAX_NUM_SEQS = 256

# Embedding model defaults
EMBEDDING_GPU_MEMORY_UTILIZATION = 0.05
EMBEDDING_MAX_MODEL_LEN = 512
EMBEDDING_MAX_NUM_SEQS = 1024


def load_models_config() -> Dict[str, Any]:
    """Load models configuration from models.json"""
    try:
        if os.path.exists(MODELS_CONFIG_PATH):
            with open(MODELS_CONFIG_PATH, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded models configuration from {MODELS_CONFIG_PATH}")
                # Create a lookup dictionary for quick access
                models_dict = {}
                for model in config.get('predefined_models', []):
                    models_dict[model['abbr']] = model
                    # Also index by full name for flexibility
                    models_dict[model['name']] = model
                return {
                    'models': models_dict,
                    'raw': config
                }
        else:
            logger.warning(f"Models configuration file not found at {MODELS_CONFIG_PATH}")
            return {'models': {}, 'raw': {'predefined_models': []}}
    except Exception as e:
        logger.error(f"Failed to load models configuration: {e}")
        return {'models': {}, 'raw': {'predefined_models': []}}


# Load models configuration at module import
MODELS_CONFIG = load_models_config()