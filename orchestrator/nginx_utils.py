"""
Nginx configuration management for model routing.
"""
import os
import logging
from typing import List, Dict, Any
from config import MODEL_CONTAINER_PREFIX, NGINX_CONTAINER
from docker_cli_wrapper import docker_cli

logger = logging.getLogger(__name__)


def generate_nginx_config(models: List[Dict[str, Any]]) -> str:
    """
    Generate Nginx configuration for model routing.

    Args:
        models: List of model dictionaries with abbr, port, and container info

    Returns:
        Nginx configuration as string
    """
    config = """
# Auto-generated model routing configuration
"""
    for model in models:
        config += f"""
# Model: {model['abbr']} (OpenAI-compatible API)

# Route chat/completions through orchestrator for smart context management
location = /api/v1/{model['abbr']}/chat/completions {{
    proxy_pass http://orchestrator/api/v1/{model['abbr']}/chat/completions;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    # CORS headers for browser access
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key' always;

    # Handle preflight requests
    if ($request_method = 'OPTIONS') {{
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key';
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }}

    # SSE support for streaming
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}}

# Route all other endpoints directly to model
location /api/v1/{model['abbr']}/ {{
    proxy_pass http://{MODEL_CONTAINER_PREFIX}{model['abbr']}:8000/v1/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    # CORS headers for browser access
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key' always;

    # Handle preflight requests
    if ($request_method = 'OPTIONS') {{
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key';
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }}

    # SSE support for streaming
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}}
"""
    return config


def update_nginx_config(redis_client) -> bool:
    """
    Generate and update Nginx configuration based on running models.

    Args:
        redis_client: Redis connection for getting model state

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get all running models
        models = []
        for key in redis_client.keys("model:*"):
            model_data = redis_client.hgetall(key)
            if model_data.get("status") == "running":
                models.append({
                    "abbr": model_data["abbr"],
                    "port": model_data.get("port", "8000"),
                    "container": model_data.get("container_id", "")[:12] if model_data.get("container_id") else ""
                })

        # Generate configuration
        config = generate_nginx_config(models)

        # Write config files
        config_paths = [
            "/configs/model_routes.conf",  # Legacy path
            "/nginx-config/model_routes.conf"  # Current path
        ]

        for path in config_paths:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(config)
                logger.info(f"Updated nginx config at {path}")
            except Exception as e:
                logger.warning(f"Could not write to {path}: {e}")

        # Reload Nginx
        try:
            if docker_cli and docker_cli.available:
                docker_cli.container_exec(NGINX_CONTAINER, ["nginx", "-s", "reload"])
                logger.info(f"Reloaded Nginx with {len(models)} model routes")
        except Exception as e:
            logger.warning(f"Could not reload Nginx: {e}")

        return True

    except Exception as e:
        logger.error(f"Failed to update Nginx config: {e}")
        return False


def get_nginx_status() -> Dict[str, Any]:
    """
    Get Nginx container status.

    Returns:
        Dictionary with Nginx status information
    """
    try:
        if docker_cli and docker_cli.available:
            if docker_cli.container_running(NGINX_CONTAINER):
                return {
                    "running": True,
                    "container": NGINX_CONTAINER,
                    "config_path": "/nginx-config/model_routes.conf"
                }
        return {"running": False, "error": "Nginx container not running"}
    except Exception as e:
        return {"running": False, "error": str(e)}