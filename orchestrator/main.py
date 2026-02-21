"""
Multi-Model Orchestrator - Refactored Main Application
Manages deployment and lifecycle of multiple LLM and embedding models.
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Import our modules
from config import (
    MODELS_CONFIG, ORCHESTRATOR_PORT, JWT_SECRET,
    SESSION_TIMEOUT, load_models_config
)
from models import (
    ModelType, ModelConfig, ModelStatus, CachedModel,
    scan_cached_models, get_model_config_from_json
)
from gpu_utils import get_gpu_stats, get_gpu_processes, get_available_gpu
from docker_manager import (
    check_docker_available, build_container_config,
    deploy_container, stop_model_container, remove_model_container,
    get_container_logs, sync_container_state
)
from nginx_utils import update_nginx_config
from redis_utils import (
    get_redis_client, get_free_port, save_model_state,
    get_model_state, update_model_status, delete_model_state,
    list_models, create_api_key, verify_api_key, list_api_keys,
    delete_api_key
)
from auth import (
    LoginRequest, TokenResponse,
    authenticate_user, create_access_token,
    verify_token, verify_token_optional
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Multi-Model Orchestrator")

# Redis connection
r = get_redis_client()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= Authentication Endpoints =============

@app.post("/auth/login", response_model=TokenResponse)
async def login(login_request: LoginRequest):
    """Login endpoint to get JWT token"""
    if not authenticate_user(login_request.username, login_request.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    access_token_expires = timedelta(hours=SESSION_TIMEOUT)
    access_token = create_access_token(
        data={"sub": login_request.username},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=SESSION_TIMEOUT * 3600
    )


@app.get("/auth/verify")
async def verify_auth(username: str = Depends(verify_token)):
    """Verify if token is valid"""
    return {"authenticated": True, "username": username}


# ============= Model Management Endpoints =============

@app.post("/models/deploy")
async def deploy_model(
    config: ModelConfig,
    background_tasks: BackgroundTasks,
    username: str = Depends(verify_token)
):
    """Deploy a new model container"""
    if not check_docker_available():
        raise HTTPException(500, "Docker connection not available")

    # Check if model already exists
    existing = get_model_state(r, config.abbr)
    if existing and existing.get("status") == "running":
        raise HTTPException(400, f"Model {config.abbr} is already running")

    # Assign resources
    config.port = config.port or get_free_port(r)
    config.gpu_device = config.gpu_device if config.gpu_device is not None else get_available_gpu(r)

    # Save initial state
    save_model_state(r, config.abbr, {
        "abbr": config.abbr,
        "name": config.name,
        "type": config.type.value,
        "status": "deploying",
        "port": config.port,
        "gpu_device": config.gpu_device,
        "endpoint": f"/api/v1/{config.abbr}",
        "progress": "0",
        "progress_message": "Initializing deployment...",
        "quantization": config.quantization or "none",
        "max_model_len": config.max_model_len,
        "gpu_memory_utilization": config.gpu_memory_utilization,
        "max_num_seqs": config.max_num_seqs
    })

    # Build container configuration
    container_config = build_container_config(config, config.port)

    # Deploy in background
    background_tasks.add_task(
        deploy_container,
        config,
        container_config,
        config.port,
        r,
        lambda: update_nginx_config(r)
    )

    return {
        "status": "deploying",
        "abbr": config.abbr,
        "gpu_device": config.gpu_device,
        "endpoint": f"/api/v1/{config.abbr}"
    }


@app.post("/models/{abbr}/stop")
async def stop_model(abbr: str, username: str = Depends(verify_token)):
    """Stop a running model"""
    model_state = get_model_state(r, abbr)
    if not model_state:
        raise HTTPException(404, f"Model {abbr} not found")

    if model_state.get("status") != "running":
        raise HTTPException(400, f"Model {abbr} is not running")

    # Stop container
    if stop_model_container(abbr):
        update_model_status(r, abbr, "stopped")
        update_nginx_config(r)
        return {"status": "stopped", "abbr": abbr}
    else:
        raise HTTPException(500, f"Failed to stop model {abbr}")


@app.post("/models/{abbr}/start")
async def start_model(
    abbr: str,
    background_tasks: BackgroundTasks,
    username: str = Depends(verify_token)
):
    """Re-start a stopped model"""
    model_state = get_model_state(r, abbr)
    if not model_state:
        raise HTTPException(404, f"Model {abbr} not found")

    if model_state.get("status") == "running":
        raise HTTPException(400, f"Model {abbr} is already running")

    # Recreate ModelConfig from stored data
    config = ModelConfig(
        name=model_state["name"],
        abbr=model_state["abbr"],
        type=ModelType(model_state["type"]),
        quantization=model_state.get("quantization") if model_state.get("quantization") != "none" else None,
        max_model_len=int(model_state.get("max_model_len", 4096)),
        gpu_memory_utilization=float(model_state.get("gpu_memory_utilization", 0.9)),
        max_num_seqs=int(model_state.get("max_num_seqs", 256)),
        gpu_device=int(model_state.get("gpu_device", 0)),
        port=int(model_state.get("port", get_free_port(r)))
    )

    # Update status
    update_model_status(r, abbr, "deploying", 0, "Restarting model...")

    # Build and deploy container
    container_config = build_container_config(config, config.port)
    background_tasks.add_task(
        deploy_container,
        config,
        container_config,
        config.port,
        r,
        lambda: update_nginx_config(r)
    )

    return {"status": "deploying", "abbr": abbr}


@app.delete("/models/{abbr}")
async def delete_model(abbr: str, username: str = Depends(verify_token)):
    """Permanently delete a model and its configuration"""
    model_state = get_model_state(r, abbr)
    if not model_state:
        raise HTTPException(404, f"Model {abbr} not found")

    # Stop and remove container
    stop_model_container(abbr)
    remove_model_container(abbr)

    # Delete from Redis
    delete_model_state(r, abbr)

    # Update Nginx
    update_nginx_config(r)

    return {"status": "deleted", "abbr": abbr}


@app.get("/models/{abbr}/logs")
async def get_model_logs(
    abbr: str,
    lines: int = 50,
    username: str = Depends(verify_token)
):
    """Get logs from a model container"""
    model_state = get_model_state(r, abbr)
    if not model_state:
        raise HTTPException(404, f"Model {abbr} not found")

    logs = get_container_logs(abbr, lines)
    return {"abbr": abbr, "logs": logs}


# ============= Status and Information Endpoints =============

@app.get("/models")
async def list_all_models(username: str = Depends(verify_token)):
    """List all deployed models with their status"""
    models = []
    for model_data in list_models(r):
        # Check if model is in cache
        cached_models = scan_cached_models()
        is_cached = any(cm.name == model_data.get("name") for cm in cached_models)

        models.append(ModelStatus(
            abbr=model_data["abbr"],
            name=model_data["name"],
            type=ModelType(model_data["type"]),
            status=model_data["status"],
            container_id=model_data.get("container_id"),
            port=int(model_data["port"]) if model_data.get("port") else None,
            endpoint=model_data.get("endpoint", f"/api/v1/{model_data['abbr']}"),
            metrics=None,
            progress=int(model_data["progress"]) if model_data.get("progress") else None,
            progress_message=model_data.get("progress_message"),
            cached=is_cached,
            gpu_device=int(model_data["gpu_device"]) if model_data.get("gpu_device") else None
        ))

    return models


@app.get("/cached-models")
async def list_cached_models():
    """List all models available in the HuggingFace cache"""
    return scan_cached_models()


@app.get("/available-models")
async def list_available_models():
    """List all predefined models from models.json"""
    # Reload configuration to get latest changes
    config = load_models_config()
    return config['raw'].get('predefined_models', [])


@app.get("/gpu-stats")
async def gpu_stats():
    """Get GPU statistics and usage information"""
    stats = get_gpu_stats()
    processes = get_gpu_processes()

    # Add model assignments
    for gpu_stat in stats:
        gpu_idx = gpu_stat["index"]
        gpu_stat["models"] = []

        # Find models assigned to this GPU
        for model_data in list_models(r, status_filter="running"):
            if int(model_data.get("gpu_device", -1)) == gpu_idx:
                gpu_stat["models"].append({
                    "abbr": model_data["abbr"],
                    "name": model_data["name"],
                    "type": model_data["type"]
                })

        # Add processes if any
        gpu_stat["processes"] = processes.get(gpu_idx, [])

    return {"gpus": stats}


# ============= API Key Management =============

@app.post("/api-keys")
async def create_new_api_key(
    name: str,
    username: str = Depends(verify_token)
):
    """Create a new API key"""
    api_key = create_api_key(r, name)
    return {"api_key": api_key, "name": name}


@app.get("/api-keys")
async def list_all_api_keys(username: str = Depends(verify_token)):
    """List all API keys"""
    return list_api_keys(r)


@app.delete("/api-keys/{key}")
async def delete_existing_api_key(
    key: str,
    username: str = Depends(verify_token)
):
    """Delete an API key"""
    if delete_api_key(r, key):
        return {"status": "deleted"}
    raise HTTPException(404, "API key not found")


# ============= Model Inference Proxy =============

@app.post("/api/v1/{model_abbr}/chat/completions")
async def proxy_chat_completion(
    model_abbr: str,
    request: Request,
    x_api_key: Optional[str] = Header(None)
):
    """
    Proxy chat completion requests to model containers.
    Handles smart context truncation and streaming.
    """
    # Verify API key - required for all /api requests
    if not x_api_key:
        raise HTTPException(401, "API key required")
    if not verify_api_key(r, x_api_key):
        raise HTTPException(401, "Invalid API key")

    # Check model exists and is running
    model_state = get_model_state(r, model_abbr)
    if not model_state:
        raise HTTPException(404, f"Model {model_abbr} not found")
    if model_state.get("status") != "running":
        raise HTTPException(503, f"Model {model_abbr} is not running")

    # Get request body
    body = await request.json()

    # Get model configuration for context limits
    model_config = get_model_config_from_json(model_abbr, model_state.get("name"))
    max_context = int(model_state.get("max_model_len", 4096))

    # Smart context truncation
    if "messages" in body:
        messages = body["messages"]
        # Simple truncation - keep system message and recent messages
        if len(messages) > 10:
            system_msgs = [m for m in messages if m.get("role") == "system"]
            other_msgs = [m for m in messages if m.get("role") != "system"]
            body["messages"] = system_msgs + other_msgs[-9:]

    # Proxy to model container
    container_name = f"MIND_MODEL_{model_abbr}"
    model_url = f"http://{container_name}:8000/v1/chat/completions"

    try:
        # Handle streaming
        if body.get("stream", False):
            async def stream_response():
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", model_url, json=body) as response:
                        async for chunk in response.aiter_bytes():
                            yield chunk

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream"
            )
        else:
            # Regular request
            async with httpx.AsyncClient() as client:
                response = await client.post(model_url, json=body, timeout=60.0)
                return response.json()

    except httpx.TimeoutException:
        raise HTTPException(504, "Model request timed out")
    except Exception as e:
        logger.error(f"Error proxying request to {model_abbr}: {e}")
        raise HTTPException(500, f"Error processing request: {str(e)}")


@app.api_route("/api/v1/{model_abbr}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_model_api(
    model_abbr: str,
    path: str,
    request: Request,
    x_api_key: Optional[str] = Header(None)
):
    """
    Generic proxy for all /api/v1/ model endpoints.
    Requires API key authentication then forwards to model containers.
    """
    # Verify API key - required for all /api requests
    if not x_api_key:
        raise HTTPException(401, "API key required")
    if not verify_api_key(r, x_api_key):
        raise HTTPException(401, "Invalid API key")

    # Check model exists and is running
    model_state = get_model_state(r, model_abbr)
    if not model_state:
        raise HTTPException(404, f"Model {model_abbr} not found")
    if model_state.get("status") != "running":
        raise HTTPException(503, f"Model {model_abbr} is not running")

    # Get container name
    container_name = f"MIND_MODEL_{model_abbr}"
    target_url = f"http://{container_name}:8000/v1/{path}"

    # Forward the request
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # Build the request
            headers = dict(request.headers)
            # Remove hop-by-hop headers
            headers.pop('host', None)
            headers.pop('x-api-key', None)

            # Get request body if present
            body = None
            if request.method in ["POST", "PUT"]:
                body = await request.body()

            # Forward the request
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=dict(request.query_params),
                timeout=300.0
            )

            # Return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )

    except httpx.ConnectError:
        raise HTTPException(503, f"Model container {model_abbr} is not responding")
    except Exception as e:
        logger.error(f"Error proxying request to {model_abbr}: {e}")
        raise HTTPException(500, f"Error processing request: {str(e)}")


# ============= Health and Startup =============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "docker": check_docker_available(),
        "redis": r.ping()
    }


@app.on_event("startup")
async def startup_event():
    """Initialize the orchestrator on startup"""
    logger.info("Starting Multi-Model Orchestrator")

    # Check Docker availability
    if not check_docker_available():
        logger.error("Docker is not available - model deployment will not work")

    # Sync container state
    logger.info("Starting container state synchronization...")
    sync_result = sync_container_state(r)
    logger.info(f"Found {len(sync_result['running'])} running models")

    # Update Nginx configuration
    update_nginx_config(r)

    logger.info("Orchestrator startup completed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ORCHESTRATOR_PORT)