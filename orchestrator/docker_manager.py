"""
Docker container management for model deployments.
"""
import os
import asyncio
import logging
from typing import Dict, Any, Optional, List
from docker_cli_wrapper import docker_cli
from models import ModelConfig, ModelType, get_model_settings, build_vllm_command
from config import (
    HOST_CACHE_DIR, HOST_MODELS_DIR, MODELS_DIR,
    MODEL_CONTAINER_PREFIX, NETWORK_NAME, VLLM_DEFAULT_PORT,
    HF_TOKEN
)

logger = logging.getLogger(__name__)

# Docker client instance
docker_client = docker_cli

if docker_client.available:
    logger.info("Docker CLI wrapper is ready")
    if docker_client.ping():
        logger.info("Docker daemon is responsive")
    else:
        logger.error("Docker daemon not responding")
else:
    logger.error("Docker CLI not available - deployment will not work")
    docker_client = None


def check_docker_available() -> bool:
    """Check if Docker client is available"""
    return docker_client is not None and docker_client.available


def build_container_config(config: ModelConfig, port: int) -> Dict[str, Any]:
    """
    Build Docker container configuration for a model.

    Args:
        config: ModelConfig object
        port: Port to expose the model on

    Returns:
        Dictionary with Docker container configuration
    """
    container_name = f"{MODEL_CONTAINER_PREFIX}{config.abbr}"

    # Base configuration
    container_config = {
        "image": "vllm/vllm-openai:latest",
        "name": container_name,
        "detach": True,
        "environment": {
            "NVIDIA_VISIBLE_DEVICES": str(config.gpu_device),
            "CUDA_VISIBLE_DEVICES": str(config.gpu_device),
            "HF_TOKEN": HF_TOKEN
        },
        "volumes": {
            os.path.expanduser(HOST_MODELS_DIR): {"bind": MODELS_DIR, "mode": "rw"},
            os.path.expanduser(HOST_CACHE_DIR): {"bind": "/root/.cache", "mode": "rw"}
        },
        "network": NETWORK_NAME,
        "restart_policy": {"Name": "unless-stopped"},
        "device_requests": [{
            "count": -1,
            "capabilities": [["gpu"]]
        }],
        "labels": {
            "model.abbr": config.abbr,
            "model.gpu": str(config.gpu_device),
            "model.name": config.name,
            "model.type": config.type.value
        }
    }

    # Get optimized settings and build command
    settings = get_model_settings(config)
    cmd = build_vllm_command(config, settings, VLLM_DEFAULT_PORT)
    container_config["command"] = cmd

    return container_config


async def deploy_container(
    config: ModelConfig,
    container_config: Dict[str, Any],
    port: int,
    redis_client,
    update_nginx_callback=None
) -> bool:
    """
    Deploy a model container asynchronously.

    Args:
        config: ModelConfig object
        container_config: Docker container configuration
        port: Port assigned to the model
        redis_client: Redis connection for state updates
        update_nginx_callback: Optional callback to update Nginx configuration

    Returns:
        True if deployment successful, False otherwise
    """
    abbr = config.abbr

    try:
        # Update status: Starting container
        redis_client.hset(f"model:{abbr}", mapping={
            "progress": "10",
            "progress_message": "Starting container..."
        })

        # Remove existing container if any
        try:
            docker_client.container_remove(container_config["name"], force=True)
        except:
            pass

        # Create and start container
        container_id = docker_client.container_run(
            image=container_config["image"],
            name=container_config["name"],
            command=container_config.get("command"),
            environment=container_config.get("environment"),
            volumes=container_config.get("volumes"),
            network=container_config.get("network"),
            device_requests=container_config.get("device_requests"),
            restart_policy=container_config.get("restart_policy"),
            detach=container_config.get("detach", True),
            ports=container_config.get("ports")
        )

        if not container_id:
            raise Exception("Failed to create container")

        # Update status: Container started
        redis_client.hset(f"model:{abbr}", mapping={
            "container_id": container_id,
            "progress": "30",
            "progress_message": "Container started, loading model..."
        })

        # Wait for model to be ready
        max_retries = 60  # 5 minutes timeout
        retry_count = 0

        while retry_count < max_retries:
            await asyncio.sleep(5)

            # Check container is still running
            container_status = docker_client.container_status(container_config["name"])
            if container_status != "running":
                # Get container logs for debugging
                logs = docker_client.container_logs(container_config["name"], tail=50)
                logger.error(f"Container {container_config['name']} stopped unexpectedly (status: {container_status})")
                logger.error(f"Container logs:\n{logs}")
                raise Exception(f"Container stopped unexpectedly (status: {container_status})")

            # Check if vLLM is ready
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://{container_config['name']}:8000/health")
                    if response.status_code == 200:
                        logger.info(f"Model {abbr} is ready")
                        break
            except:
                pass

            # Update progress
            progress = min(30 + (retry_count * 70 // max_retries), 95)
            redis_client.hset(f"model:{abbr}", mapping={
                "progress": str(progress),
                "progress_message": f"Loading model... ({retry_count * 5}s)"
            })

            retry_count += 1

        if retry_count >= max_retries:
            raise Exception("Timeout waiting for model to load")

        # Update status: Model ready
        redis_client.hset(f"model:{abbr}", mapping={
            "status": "running",
            "progress": "100",
            "progress_message": "Model ready"
        })

        # Update Nginx configuration
        if update_nginx_callback:
            update_nginx_callback()

        logger.info(f"Successfully deployed model {abbr}")
        return True

    except Exception as e:
        logger.error(f"Failed to deploy model {abbr}: {e}")
        redis_client.hset(f"model:{abbr}", mapping={
            "status": "error",
            "progress": "0",
            "progress_message": f"Deployment failed: {str(e)}"
        })
        return False


def stop_model_container(abbr: str) -> bool:
    """
    Stop a model container.

    Args:
        abbr: Model abbreviation

    Returns:
        True if successful, False otherwise
    """
    container_name = f"{MODEL_CONTAINER_PREFIX}{abbr}"

    try:
        container_status = docker_client.container_status(container_name)
        if container_status == "running":
            docker_client.container_stop(container_name)
            logger.info(f"Stopped container {container_name}")
            return True
        else:
            logger.warning(f"Container {container_name} is not running (status: {container_status})")
            return False
    except Exception as e:
        logger.error(f"Failed to stop container {container_name}: {e}")
        return False


def remove_model_container(abbr: str) -> bool:
    """
    Remove a model container.

    Args:
        abbr: Model abbreviation

    Returns:
        True if successful, False otherwise
    """
    container_name = f"{MODEL_CONTAINER_PREFIX}{abbr}"

    try:
        docker_client.container_remove(container_name, force=True)
        logger.info(f"Removed container {container_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove container {container_name}: {e}")
        return False


def get_container_logs(abbr: str, lines: int = 50) -> str:
    """
    Get logs from a model container.

    Args:
        abbr: Model abbreviation
        lines: Number of lines to retrieve

    Returns:
        Container logs as string
    """
    container_name = f"{MODEL_CONTAINER_PREFIX}{abbr}"

    try:
        return docker_client.container_logs(container_name, tail=lines)
    except Exception as e:
        logger.error(f"Failed to get logs for {container_name}: {e}")
        return f"Error getting logs: {e}"


def sync_container_state(redis_client) -> Dict[str, List[str]]:
    """
    Synchronize running containers with Redis state.

    Args:
        redis_client: Redis connection

    Returns:
        Dictionary with running and stopped model lists
    """
    try:
        # Get all running model containers
        running_containers = docker_client.container_list()

        running_models = []
        for container in running_containers:
            # Extract model abbreviation from container name
            # Docker ps returns "Names" not "name"
            container_name = container.get("Names", container.get("name", ""))
            if container_name.startswith(MODEL_CONTAINER_PREFIX):
                abbr = container_name[len(MODEL_CONTAINER_PREFIX):]
                running_models.append(abbr)

                # Update Redis state if needed
                model_key = f"model:{abbr}"
                if redis_client.exists(model_key):
                    current_status = redis_client.hget(model_key, "status")
                    if current_status != "running":
                        redis_client.hset(model_key, "status", "running")
                        logger.info(f"Updated {abbr} status to running")

        # Check for stopped models in Redis
        stopped_models = []
        for key in redis_client.keys("model:*"):
            abbr = key.split(":")[1]
            if abbr not in running_models:
                status = redis_client.hget(key, "status")
                if status == "running":
                    redis_client.hset(key, "status", "stopped")
                    stopped_models.append(abbr)
                    logger.info(f"Updated {abbr} status to stopped")

        return {
            "running": running_models,
            "stopped": stopped_models
        }

    except Exception as e:
        logger.error(f"Failed to sync container state: {e}")
        return {"running": [], "stopped": []}