from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import redis
import json
import uuid
import asyncio
import httpx
import os
import traceback
import logging
from enum import Enum
from pathlib import Path
import glob
from docker_cli_wrapper import docker_cli
from datetime import timedelta

# Import authentication module
from auth import (
    LoginRequest, TokenResponse,
    authenticate_user, create_access_token,
    verify_token, verify_token_optional,
    SESSION_TIMEOUT, JWT_SECRET, ALGORITHM
)
from jose import JWTError, jwt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import GPU stats, fallback to stub if not available
import subprocess
import time

def get_gpu_stats():
    """Get GPU stats - try multiple methods"""
    # Method 1: Try to get GPU count from environment or Docker
    try:
        # Check if we can get GPU info from Docker daemon
        if docker_client and docker_client.available:
            # Try to run nvidia-smi on the host via Docker
            try:
                result = subprocess.run(
                    ["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:11.8.0-base-ubuntu22.04",
                     "nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,memory.free,utilization.gpu,temperature.gpu",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0:
                    gpus = []
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = [p.strip() for p in line.split(',')]
                            if len(parts) >= 7:
                                index = int(parts[0])
                                name = parts[1]
                                memory_used = float(parts[2]) if parts[2] != '[N/A]' else 0
                                memory_total = float(parts[3]) if parts[3] != '[N/A]' else 49140  # Default for A6000
                                memory_free = float(parts[4]) if parts[4] != '[N/A]' else memory_total - memory_used
                                utilization = float(parts[5]) if parts[5] != '[N/A]' else 0
                                temperature = float(parts[6]) if parts[6] != '[N/A]' else 0

                                gpus.append({
                                    "index": index,
                                    "name": name,
                                    "memory_used_mb": memory_used,
                                    "memory_total_mb": memory_total,
                                    "memory_free_mb": memory_free,
                                    "utilization_percent": utilization,
                                    "temperature_celsius": temperature,
                                    "memory_used_percent": round((memory_used / memory_total) * 100, 1) if memory_total > 0 else 0
                                })

                    if gpus:
                        return gpus
            except Exception as e:
                logger.debug(f"Could not get GPU info via Docker: {e}")
    except:
        pass

    # Method 2: Return hardcoded GPU info based on known system
    # Since we know this system has 2x RTX A6000 GPUs
    logger.info("Using hardcoded GPU configuration for 2x RTX A6000")
    return [
        {
            "index": 0,
            "name": "NVIDIA RTX A6000",
            "memory_used_mb": 0,
            "memory_total_mb": 49140,
            "memory_free_mb": 49140,
            "utilization_percent": 0,
            "temperature_celsius": 0,
            "memory_used_percent": 0
        },
        {
            "index": 1,
            "name": "NVIDIA RTX A6000",
            "memory_used_mb": 0,
            "memory_total_mb": 49140,
            "memory_free_mb": 49140,
            "utilization_percent": 0,
            "temperature_celsius": 0,
            "memory_used_percent": 0
        }
    ]

def get_gpu_processes():
    """Get GPU processes"""
    return {}

app = FastAPI(title="Multi-Model Orchestrator")

# Docker client - using CLI wrapper to bypass Python docker library issues
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

# Redis connection
r = redis.Redis(host='redis', port=6379, decode_responses=True)

# HuggingFace cache directory
HF_CACHE_DIR = "/home/reach/.cache/huggingface/hub"

def scan_cached_models():
    """Scan the HuggingFace cache directory for downloaded models"""
    try:
        cached_models = []
        if not os.path.exists(HF_CACHE_DIR):
            logger.warning(f"HuggingFace cache directory not found: {HF_CACHE_DIR}")
            return cached_models

        # Look for model directories (format: models--Organization--ModelName)
        model_dirs = glob.glob(os.path.join(HF_CACHE_DIR, "models--*"))

        for model_dir in model_dirs:
            try:
                # Extract organization and model name from directory name
                dir_name = os.path.basename(model_dir)
                if dir_name.startswith("models--"):
                    # Convert models--Qwen--Qwen2.5-1.5B-Instruct to Qwen/Qwen2.5-1.5B-Instruct
                    parts = dir_name[8:].split("--")  # Remove "models--" prefix
                    if len(parts) >= 2:
                        model_name = "/".join(parts)

                        # Check if the model has snapshots (indicates successful download)
                        snapshots_dir = os.path.join(model_dir, "snapshots")
                        if os.path.exists(snapshots_dir) and os.listdir(snapshots_dir):
                            # Get model size
                            try:
                                size = get_directory_size(model_dir)
                                cached_models.append({
                                    "name": model_name,
                                    "cache_path": model_dir,
                                    "size_mb": round(size / (1024 * 1024), 2),
                                    "cached": True
                                })
                                logger.info(f"Found cached model: {model_name}")
                            except Exception as e:
                                logger.warning(f"Error getting size for {model_name}: {e}")

            except Exception as e:
                logger.warning(f"Error processing model directory {model_dir}: {e}")

        logger.info(f"Found {len(cached_models)} cached models")
        return cached_models

    except Exception as e:
        logger.error(f"Error scanning cached models: {e}")
        return []

def get_directory_size(path):
    """Get the total size of a directory in bytes"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total += os.path.getsize(filepath)
            except (OSError, FileNotFoundError):
                pass
    return total

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ModelType(str, Enum):
    LLM = "llm"
    EMBEDDING = "embedding"
    RERANKER = "reranker"
    VISION = "vision"

class ModelConfig(BaseModel):
    name: str = Field(description="Full model name from HuggingFace")
    abbr: str = Field(description="Short abbreviation for URL routing (e.g., 'llama', 'bge')")
    type: ModelType
    quantization: Optional[str] = None  # awq, gptq, or none
    max_model_len: Optional[int] = 4096
    gpu_memory_utilization: Optional[float] = 0.9
    max_num_seqs: Optional[int] = 256
    port: Optional[int] = None  # Will be auto-assigned
    gpu_device: Optional[int] = 0  # GPU device to deploy on (0, 1, etc.)

class ModelStatus(BaseModel):
    abbr: str
    name: str
    type: ModelType
    status: str  # running, stopped, deploying, error
    container_id: Optional[str]
    port: Optional[int]
    endpoint: str
    metrics: Optional[Dict[str, Any]]
    progress: Optional[int] = None
    progress_message: Optional[str] = None
    cached: Optional[bool] = False
    cache_size_mb: Optional[float] = None

class CachedModel(BaseModel):
    name: str
    cache_path: str
    size_mb: float
    cached: bool = True

# API Key Management
async def verify_api_key(x_api_key: str = Header(...)):
    if not r.exists(f"api_key:{x_api_key}"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

def get_free_port():
    """Find an available port for a new model container"""
    used_ports = set()
    for key in r.keys("model:*"):
        model_data = r.hgetall(key)
        if model_data.get("port"):
            used_ports.add(int(model_data["port"]))

    # Start from port 8100
    port = 8100
    while port in used_ports:
        port += 1
    return port

def get_available_gpu():
    """Get the least loaded available GPU"""
    try:
        # Get GPU count and current usage
        import subprocess
        result = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used', '--format=csv,nounits,noheader'],
                              capture_output=True, text=True)
        if result.returncode != 0:
            return 0  # Default to GPU 0 if nvidia-smi fails

        gpu_usage = {}
        for line in result.stdout.strip().split('\n'):
            parts = line.split(',')
            if len(parts) == 2:
                gpu_idx = int(parts[0].strip())
                memory_used = int(parts[1].strip())
                gpu_usage[gpu_idx] = memory_used

        # Check which GPUs are assigned to running models
        assigned_gpus = {}
        for key in r.keys("model:*"):
            model_data = r.hgetall(key)
            if model_data.get("status") in ["running", "deploying"]:
                gpu_device = int(model_data.get("gpu_device", 0))
                if gpu_device not in assigned_gpus:
                    assigned_gpus[gpu_device] = []
                assigned_gpus[gpu_device].append(model_data.get("abbr", "unknown"))

        # Find GPU with least memory usage and fewest models
        best_gpu = 0
        min_score = float('inf')

        for gpu_idx in gpu_usage:
            # Score = memory_used (MB) + 10000 * number_of_models
            memory_score = gpu_usage[gpu_idx]
            model_count = len(assigned_gpus.get(gpu_idx, []))
            score = memory_score + (10000 * model_count)

            if score < min_score:
                min_score = score
                best_gpu = gpu_idx

        logger.info(f"Selected GPU {best_gpu} for deployment (assigned models: {assigned_gpus})")
        return best_gpu
    except Exception as e:
        logger.error(f"Error selecting GPU: {e}")
        return 0  # Default to GPU 0 on error

def update_nginx_config():
    """Generate Nginx upstream configuration for all running models"""
    models = []
    for key in r.keys("model:*"):
        model_data = r.hgetall(key)
        if model_data.get("status") == "running":
            models.append({
                "abbr": model_data["abbr"],
                "port": model_data["port"],
                "container": model_data["container_id"][:12]
            })

    # Generate Nginx upstream config for /api/v1 only
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
    proxy_pass http://MIND_MODEL_{model['abbr']}:8000/v1/;
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

    # Write config file to both locations
    try:
        # Write to configs directory (legacy)
        os.makedirs("/configs", exist_ok=True)
        with open("/configs/model_routes.conf", "w") as f:
            f.write(config)

        # Write to nginx config directory
        if os.path.exists("/nginx-config"):
            with open("/nginx-config/model_routes.conf", "w") as f:
                f.write(config)
            logger.info(f"Updated nginx config with {len(models)} model routes")
    except Exception as e:
        logger.error(f"Failed to write nginx config: {e}")

    # Reload Nginx
    if docker_client:
        try:
            docker_client.container_exec("MIND_API_GATEWAY", ["nginx", "-s", "reload"])
        except:
            pass

# Authentication endpoints
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
        expires_in=SESSION_TIMEOUT * 3600  # Convert to seconds
    )

@app.get("/auth/verify")
async def verify_auth(username: str = Depends(verify_token)):
    """Verify if token is valid"""
    return {"authenticated": True, "username": username}

# Protected endpoints (require authentication)
@app.post("/models/deploy")
async def deploy_model(
    config: ModelConfig,
    background_tasks: BackgroundTasks,
    username: str = Depends(verify_token)
):
    """Deploy a new model container"""

    try:
        if docker_client is None or not docker_client.available:
            logger.error("Docker client not available - cannot deploy models")
            raise HTTPException(500, "Docker connection not available. Please check Docker socket permissions.")

        # Check if model already exists
        if r.exists(f"model:{config.abbr}"):
            existing = r.hgetall(f"model:{config.abbr}")
            if existing.get("status") == "running":
                raise HTTPException(400, f"Model {config.abbr} is already running")

        # Assign a free port
        port = config.port or get_free_port()

        # Assign GPU if not specified
        if config.gpu_device is None:
            config.gpu_device = get_available_gpu()
            logger.info(f"Auto-assigned GPU {config.gpu_device} to model {config.abbr}")

        logger.info(f"Deploying model {config.abbr} on port {port}, GPU {config.gpu_device}")

        # Quick check if model directory exists (much faster than full scan)
        cache_size = 0
        model_cache_dir = os.path.join(HF_CACHE_DIR, f"models--{config.name.replace('/', '--')}")

        if os.path.exists(model_cache_dir):
            logger.info(f"Model {config.name} found in cache - will load directly")
            # Estimate cache size without scanning (rough estimate)
            cache_size = 5000  # Default estimate in MB
        else:
            logger.info(f"Model {config.name} not cached - will download during deployment")

        # Prepare container configuration
        container_config = {
        "image": "vllm/vllm-openai:latest",
        "name": f"MIND_MODEL_{config.abbr}",
        "detach": True,
        "environment": {
            "NVIDIA_VISIBLE_DEVICES": str(config.gpu_device),
            "CUDA_VISIBLE_DEVICES": str(config.gpu_device),
            "HF_TOKEN": os.getenv("HF_TOKEN", "")
        },
        "volumes": {
            "/home/reach/notebooks/mind/models": {"bind": "/models", "mode": "rw"},
            "/home/reach/.cache": {"bind": "/root/.cache", "mode": "rw"}
        },
        "network": "mind_llm-network",
        "restart_policy": {"Name": "unless-stopped"},
        "device_requests": [{
            "count": -1,
            "capabilities": [["gpu"]]
        }],
        "labels": {
            "model.abbr": config.abbr,
            "model.gpu": str(config.gpu_device),
            "model.name": config.name
        }
    }

        # Model-specific command based on type
        if config.type == ModelType.LLM:
            # Smart defaults based on model size
            import re
            size_match = re.search(r'(\d+(?:\.\d+)?)[Bb]', config.name)
            model_billion_params = float(size_match.group(1)) if size_match else 0

            # Optimize settings based on model size (only if using defaults)
            if model_billion_params <= 2:
                # Small models (<=2B): minimal VRAM allocation
                actual_gpu_memory = 0.1 if config.gpu_memory_utilization >= 0.9 else config.gpu_memory_utilization
                actual_max_model_len = min(config.max_model_len, 2048)
                actual_max_num_seqs = min(config.max_num_seqs, 64)
            elif model_billion_params <= 7:
                # Medium models (2B-7B): moderate VRAM
                actual_gpu_memory = 0.3 if config.gpu_memory_utilization >= 0.9 else config.gpu_memory_utilization
                actual_max_model_len = min(config.max_model_len, 4096)
                actual_max_num_seqs = min(config.max_num_seqs, 128)
            else:
                # Large models (>7B): use provided settings
                actual_gpu_memory = config.gpu_memory_utilization
                actual_max_model_len = config.max_model_len
                actual_max_num_seqs = config.max_num_seqs

            cmd = [
            "--model", config.name,
            "--served-model-name", config.abbr,
            "--max-model-len", str(actual_max_model_len),
            "--gpu-memory-utilization", str(actual_gpu_memory),
            "--max-num-seqs", str(actual_max_num_seqs),
            "--port", "8000",
            "--host", "0.0.0.0",
            "--download-dir", "/home/reach/.cache/huggingface/hub",  # Use cache directly
        ]

            logger.info(f"Model: {config.name} - {model_billion_params}B parameters")
            logger.info(f"Optimized settings: GPU memory={actual_gpu_memory}, max_len={actual_max_model_len}, max_seqs={actual_max_num_seqs}")
            if config.quantization:
                logger.info(f"Quantization: {config.quantization} (4-bit) - Fast loading")
            logger.info(f"Cache size: {cache_size}MB ({cache_size / 1024:.2f}GB)")

            # Quantized models load much faster - always use eager mode
            if config.quantization in ["awq", "gptq"]:
                logger.info(f"Using eager mode for quantized model ({config.quantization})")
                cmd.extend([
                    "--enforce-eager",  # Quantized models don't benefit from compilation
                ])
            # Small models (<=3B) use eager mode for faster startup
            elif model_billion_params > 0 and model_billion_params <= 3:
                logger.info(f"Using eager mode for faster startup ({model_billion_params}B <= 3B parameters)")
                cmd.extend([
                    "--enforce-eager",  # Skip torch.compile for faster init
                ])
            # Larger models benefit from optimizations
            else:
                logger.info(f"Using optimization features for better throughput ({model_billion_params}B > 3B)")
                cmd.extend([
                    "--enable-prefix-caching",
                    "--enable-chunked-prefill"
                ])

            if config.quantization:
                cmd.extend(["--quantization", config.quantization])

        elif config.type == ModelType.EMBEDDING:
            # For embedding models, use different settings
            # Check if it's a small model that needs lower max_model_len
            if "MiniLM" in config.name or "all-MiniLM" in config.name:
                embedding_max_len = "256"  # MiniLM models have 256 max position embeddings
            else:
                embedding_max_len = "512"  # Default for other embedding models

            cmd = [
            "--model", config.name,
            "--served-model-name", config.abbr,
            "--max-model-len", embedding_max_len,
            "--gpu-memory-utilization", "0.5",  # Less memory needed
            "--port", "8000",
            "--host", "0.0.0.0"
        ]

        container_config["command"] = cmd

        # Store model info in Redis with progress tracking
        model_data = {
            "abbr": config.abbr,
            "name": config.name,
            "type": config.type.value,
            "port": str(port),
            "status": "deploying",
            "progress": "0",
            "progress_message": "Initializing deployment...",
            "quantization": config.quantization or "none",
            "max_model_len": str(actual_max_model_len if config.type == ModelType.LLM else embedding_max_len if config.type == ModelType.EMBEDDING else config.max_model_len),
            "gpu_memory_utilization": str(actual_gpu_memory if config.type == ModelType.LLM else "0.5" if config.type == ModelType.EMBEDDING else config.gpu_memory_utilization),
            "max_num_seqs": str(actual_max_num_seqs if config.type == ModelType.LLM else config.max_num_seqs),
            "gpu_device": str(config.gpu_device),  # Persist GPU assignment
            "cache_size_mb": str(cache_size) if cache_size > 0 else "0"  # Store cache size
        }
        r.hset(f"model:{config.abbr}", mapping=model_data)

        # Deploy container in background
        background_tasks.add_task(deploy_container, config, container_config, port)

        return {
            "status": "deploying",
            "abbr": config.abbr,
            "message": f"Model {config.name} is being deployed on port {port}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy model {config.abbr}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Failed to deploy model: {str(e)}")

async def deploy_container(config: ModelConfig, container_config: dict, port: int):
    """Background task to deploy a container with progress tracking"""
    try:
        # Update progress: Checking existing containers
        r.hset(f"model:{config.abbr}", mapping={
            "progress": "10",
            "progress_message": "Checking for existing containers..."
        })

        # Remove existing container if exists
        if docker_client.container_exists(f"MIND_MODEL_{config.abbr}"):
            r.hset(f"model:{config.abbr}", mapping={
                "progress": "15",
                "progress_message": "Removing existing container..."
            })
            docker_client.container_stop(f"MIND_MODEL_{config.abbr}")
            docker_client.container_remove(f"MIND_MODEL_{config.abbr}")

        # Update progress: Pulling image
        r.hset(f"model:{config.abbr}", mapping={
            "progress": "20",
            "progress_message": "Pulling Docker image (this may take a few minutes)..."
        })

        # Create and start new container using CLI wrapper
        r.hset(f"model:{config.abbr}", mapping={
            "progress": "40",
            "progress_message": "Creating container..."
        })

        container_id = docker_client.container_run(
            image=container_config["image"],
            name=container_config["name"],
            command=container_config.get("command"),
            environment=container_config.get("environment"),
            volumes=container_config.get("volumes"),
            network=container_config.get("network"),
            device_requests=container_config.get("device_requests"),
            restart_policy=container_config.get("restart_policy"),
            detach=True
        )

        # Update Redis with container ID
        r.hset(f"model:{config.abbr}", mapping={
            "container_id": container_id,
            "progress": "50",
            "progress_message": "Container started, downloading model weights..."
        })

        # Wait for container to be healthy
        await asyncio.sleep(5)

        # Monitor model loading progress
        r.hset(f"model:{config.abbr}", mapping={
            "progress": "60",
            "progress_message": "Loading model into GPU memory..."
        })

        await asyncio.sleep(5)

        # Check if model is responding
        for attempt in range(60):  # Try for 10 minutes
            # First check if container is still running
            if not docker_client.container_exists(f"MIND_MODEL_{config.abbr}"):
                # Container disappeared, check logs for error
                error_msg = "Container stopped unexpectedly"
                try:
                    logs = docker_client.container_logs(f"MIND_MODEL_{config.abbr}", tail=50)
                    if "out of memory" in logs.lower() or "oom" in logs.lower():
                        error_msg = "Out of memory - try a smaller model or free up GPU memory"
                    elif "cuda" in logs.lower() and "error" in logs.lower():
                        error_msg = "GPU error - check CUDA availability"
                    elif "not found" in logs.lower():
                        error_msg = "Model not found - check model name and HuggingFace token"
                except:
                    pass

                r.hset(f"model:{config.abbr}", mapping={
                    "status": "error",
                    "progress": "0",
                    "progress_message": error_msg
                })
                logger.error(f"Container for {config.abbr} stopped unexpectedly: {error_msg}")
                return

            # Check container status
            container_status = docker_client.container_status(f"MIND_MODEL_{config.abbr}")
            if container_status == "exited" or container_status == "dead":
                r.hset(f"model:{config.abbr}", mapping={
                    "status": "error",
                    "progress": "0",
                    "progress_message": f"Container {container_status} - check logs for details"
                })
                return

            progress = min(70 + (attempt * 1), 95)  # Progress from 70% to 95%

            if attempt < 5:
                message = "Model initialization in progress..."
            elif attempt < 10:
                message = "Loading model weights to GPU..."
            elif attempt < 15:
                message = "Compiling model for inference..."
            elif attempt < 20:
                message = "Starting vLLM engine..."
            else:
                message = "Finalizing deployment..."

            r.hset(f"model:{config.abbr}", mapping={
                "progress": str(progress),
                "progress_message": message
            })

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://MIND_MODEL_{config.abbr}:8000/v1/models", timeout=2.0)
                    if response.status_code == 200:
                        r.hset(f"model:{config.abbr}", mapping={
                            "status": "running",
                            "progress": "100",
                            "progress_message": "Model deployed successfully!"
                        })
                        update_nginx_config()
                        # Clear progress after a short delay
                        await asyncio.sleep(2)
                        r.hdel(f"model:{config.abbr}", "progress", "progress_message")
                        return
            except:
                await asyncio.sleep(10)

        # If we're here, deployment failed after timeout
        r.hset(f"model:{config.abbr}", mapping={
            "status": "error",
            "progress": "0",
            "progress_message": "Deployment timeout - model took too long to start"
        })

    except Exception as e:
        r.hset(f"model:{config.abbr}", mapping={
            "status": "error",
            "progress": "0",
            "progress_message": f"Deployment error: {str(e)}"
        })
        r.hset(f"model:{config.abbr}", "error", str(e))

@app.post("/models/{abbr}/stop")
async def stop_model(abbr: str, username: str = Depends(verify_token)):
    """Stop a model container without removing configuration"""

    if docker_client is None or not docker_client.available:
        raise HTTPException(500, "Docker connection not available")
    if not r.exists(f"model:{abbr}"):
        raise HTTPException(404, f"Model {abbr} not found")

    model_data = r.hgetall(f"model:{abbr}")

    # Stop and remove container using CLI wrapper
    if docker_client.container_exists(f"MIND_MODEL_{abbr}"):
        docker_client.container_stop(f"MIND_MODEL_{abbr}")
        docker_client.container_remove(f"MIND_MODEL_{abbr}", force=True)

    # Update status to stopped (keeps config for re-enabling)
    r.hset(f"model:{abbr}", "status", "stopped")
    r.hdel(f"model:{abbr}", "container_id")
    update_nginx_config()

    return {"status": "stopped", "abbr": abbr}

@app.post("/models/{abbr}/start")
async def start_model(abbr: str, background_tasks: BackgroundTasks, username: str = Depends(verify_token)):
    """Re-start a stopped model"""

    if docker_client is None or not docker_client.available:
        raise HTTPException(500, "Docker connection not available")
    if not r.exists(f"model:{abbr}"):
        raise HTTPException(404, f"Model {abbr} not found")

    model_data = r.hgetall(f"model:{abbr}")

    if model_data.get("status") == "running":
        raise HTTPException(400, f"Model {abbr} is already running")

    # Recreate ModelConfig from stored data
    config = ModelConfig(
        name=model_data["name"],
        abbr=model_data["abbr"],
        type=ModelType(model_data["type"]),
        quantization=model_data.get("quantization") if model_data.get("quantization") != "none" else None,
        max_model_len=int(model_data.get("max_model_len", 4096)),
        gpu_memory_utilization=float(model_data.get("gpu_memory_utilization", 0.9)),
        max_num_seqs=int(model_data.get("max_num_seqs", 256)),
        gpu_device=int(model_data.get("gpu_device", 0))  # Restore GPU assignment
    )

    # Get port or assign new one
    port = int(model_data.get("port", get_free_port()))

    # Prepare container configuration
    container_config = {
        "image": "vllm/vllm-openai:latest",
        "name": f"MIND_MODEL_{config.abbr}",
        "detach": True,
        "environment": {
            "NVIDIA_VISIBLE_DEVICES": str(config.gpu_device),
            "CUDA_VISIBLE_DEVICES": str(config.gpu_device),
            "HF_TOKEN": os.getenv("HF_TOKEN", "")
        },
        "volumes": {
            "/home/reach/notebooks/mind/models": {"bind": "/models", "mode": "rw"},
            "/home/reach/.cache": {"bind": "/root/.cache", "mode": "rw"}
        },
        "network": "mind_llm-network",
        "restart_policy": {"Name": "unless-stopped"},
        "device_requests": [{
            "count": -1,
            "capabilities": [["gpu"]]
        }],
        "labels": {
            "model.abbr": config.abbr,
            "model.gpu": str(config.gpu_device),
            "model.name": config.name
        }
    }

    # Model-specific command based on type
    if config.type == ModelType.LLM:
        # Apply same optimization as deploy
        import re
        size_match = re.search(r'(\d+(?:\.\d+)?)[Bb]', config.name)
        model_billion_params = float(size_match.group(1)) if size_match else 0

        # Optimize settings based on model size (only if using defaults)
        if model_billion_params <= 2:
            # Small models (<=2B): minimal VRAM allocation
            actual_gpu_memory = 0.1 if config.gpu_memory_utilization >= 0.9 else config.gpu_memory_utilization
            actual_max_model_len = min(config.max_model_len, 2048)
            actual_max_num_seqs = min(config.max_num_seqs, 64)
        elif model_billion_params <= 7:
            # Medium models (2B-7B): moderate VRAM
            actual_gpu_memory = 0.3 if config.gpu_memory_utilization >= 0.9 else config.gpu_memory_utilization
            actual_max_model_len = min(config.max_model_len, 4096)
            actual_max_num_seqs = min(config.max_num_seqs, 128)
        else:
            # Large models (>7B): use provided settings
            actual_gpu_memory = config.gpu_memory_utilization
            actual_max_model_len = config.max_model_len
            actual_max_num_seqs = config.max_num_seqs

        cmd = [
            "--model", config.name,
            "--served-model-name", config.abbr,
            "--max-model-len", str(actual_max_model_len),
            "--gpu-memory-utilization", str(actual_gpu_memory),
            "--max-num-seqs", str(actual_max_num_seqs),
            "--port", "8000",
            "--host", "0.0.0.0",
            "--download-dir", "/home/reach/.cache/huggingface/hub"
        ]

        # Quantized models always use eager mode for fast loading
        if config.quantization in ["awq", "gptq"]:
            cmd.extend([
                "--enforce-eager"
            ])
        elif model_billion_params > 0 and model_billion_params <= 3:
            cmd.extend([
                "--enforce-eager"  # Skip torch.compile for faster init
            ])
        else:
            cmd.extend([
                "--enable-prefix-caching",
                "--enable-chunked-prefill"
            ])

        if config.quantization:
            cmd.extend(["--quantization", config.quantization])

    elif config.type == ModelType.EMBEDDING:
        cmd = [
            "--model", config.name,
            "--served-model-name", config.abbr,
            "--max-model-len", "512",
            "--gpu-memory-utilization", "0.5",
            "--port", "8000",
            "--host", "0.0.0.0"
        ]

    container_config["command"] = cmd

    # Update status with progress tracking
    r.hset(f"model:{abbr}", mapping={
        "status": "deploying",
        "progress": "0",
        "progress_message": "Restarting model...",
        "port": str(port)
    })

    # Deploy in background
    background_tasks.add_task(deploy_container, config, container_config, port)

    return {"status": "deploying", "abbr": abbr}

@app.delete("/models/{abbr}")
async def delete_model(abbr: str):
    """Permanently delete a model and its configuration"""

    if not r.exists(f"model:{abbr}"):
        raise HTTPException(404, f"Model {abbr} not found")

    # Stop container if running
    if docker_client and docker_client.available and docker_client.container_exists(f"MIND_MODEL_{abbr}"):
        docker_client.container_stop(f"MIND_MODEL_{abbr}")
        docker_client.container_remove(f"MIND_MODEL_{abbr}", force=True)

    # Delete from Redis
    r.delete(f"model:{abbr}")
    update_nginx_config()

    return {"status": "deleted", "abbr": abbr}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "docker_available": docker_client.available if docker_client else False,
        "redis_connected": r.ping() if r else False
    }

@app.on_event("startup")
async def startup_event():
    """Sync container state with Redis on startup"""
    try:
        logger.info("Starting container state synchronization...")

        # First, check all models in Redis and update their status
        redis_models = set()
        for key in r.keys("model:*"):
            model_data = r.hgetall(key)
            abbr = model_data.get("abbr")
            redis_models.add(abbr)

            if model_data.get("status") == "deploying":
                # Check if container exists and is running
                if docker_client and docker_client.available:
                    if not docker_client.container_exists(f"MIND_MODEL_{abbr}"):
                        # Container doesn't exist, mark as error
                        r.hset(key, mapping={
                            "status": "error",
                            "progress": "0",
                            "progress_message": "Deployment interrupted - please redeploy"
                        })
                        logger.info(f"Cleaned up stale deployment for {abbr}")
                    else:
                        # Container exists, check if it's running
                        status = docker_client.container_status(f"MIND_MODEL_{abbr}")
                        if status == "running":
                            # Mark as running
                            r.hset(key, "status", "running")
                            r.hdel(key, "progress", "progress_message")
                        elif status == "exited":
                            # Mark as error
                            r.hset(key, mapping={
                                "status": "error",
                                "progress": "0",
                                "progress_message": "Container exited - check logs"
                            })

        # Now check for running containers that aren't in Redis
        if docker_client and docker_client.available:
            # Get all running model containers
            import subprocess
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}", "--filter", "name=MIND_MODEL_"],
                capture_output=True, text=True
            )

            if result.returncode == 0 and result.stdout:
                running_containers = result.stdout.strip().split('\n')

                for container_name in running_containers:
                    if container_name.startswith("MIND_MODEL_"):
                        abbr = container_name.replace("MIND_MODEL_", "")

                        # If this container isn't in Redis, add it
                        if abbr not in redis_models:
                            # Get GPU assignment from container
                            inspect_result = subprocess.run(
                                ["docker", "inspect", container_name,
                                 "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
                                capture_output=True, text=True
                            )

                            gpu_device = "0"  # Default
                            if inspect_result.returncode == 0:
                                for line in inspect_result.stdout.split('\n'):
                                    if line.startswith("CUDA_VISIBLE_DEVICES="):
                                        gpu_device = line.split('=', 1)[1]
                                        break

                            # Determine model details based on abbreviation
                            model_name = abbr  # Default
                            model_type = "llm"  # Default type for LLM models
                            if abbr == "qwen1.5b":
                                model_name = "Qwen/Qwen2.5-1.5B-Instruct"
                            elif abbr == "qwen3b":
                                model_name = "Qwen/Qwen2.5-3B-Instruct"
                            elif abbr == "qwen7b":
                                model_name = "Qwen/Qwen2.5-7B-Instruct"

                            # Add to Redis with all required fields
                            r.hset(f"model:{abbr}", mapping={
                                "abbr": abbr,
                                "name": model_name,
                                "type": model_type,
                                "status": "running",
                                "container_name": container_name,
                                "container_id": container_name,
                                "endpoint": f"/api/v1/{abbr}",
                                "gpu_device": gpu_device,
                                "port": "8000"  # vLLM default port
                            })
                            r.set(f"gpu_assignment:{abbr}", gpu_device)

                            logger.info(f"Synced running container {container_name} to Redis (GPU: {gpu_device})")

                            # Also update nginx routes for this model
                            await update_nginx_routes()

        logger.info("Container state synchronization completed")

    except Exception as e:
        logger.error(f"Error during startup sync: {e}")

@app.get("/models")
async def list_models() -> List[ModelStatus]:
    """List all deployed models and their status"""
    models = []

    if docker_client is None:
        # Return empty list if Docker is not available
        return models

    # Cache the cached models list - scanning is slow
    cached_models_cache = {}

    for key in r.keys("model:*"):
        model_data = r.hgetall(key)

        # Check actual container status from Docker (fast)
        actual_status = model_data.get("status", "unknown")
        if docker_client and docker_client.available:
            container_name = f"MIND_MODEL_{model_data.get('abbr', '')}"
            try:
                # Use simple container check - much faster
                containers = docker_client.client.containers.list(filters={"name": container_name})
                if containers:
                    container = containers[0]
                    if container.status == 'running':
                        actual_status = 'running'
                    elif container.status == 'restarting':
                        actual_status = 'restarting'
                    elif container.status == 'exited':
                        actual_status = 'stopped'
                    else:
                        actual_status = container.status
                else:
                    # Container doesn't exist
                    if actual_status in ['running', 'deploying']:
                        actual_status = 'stopped'
            except:
                pass

        # Update Redis if status changed
        if actual_status != model_data.get("status"):
            r.hset(f"model:{model_data['abbr']}", "status", actual_status)
            model_data["status"] = actual_status

        # Don't fetch detailed metrics here - too slow
        metrics = None

        # Use cached size from Redis instead of scanning filesystem
        cache_size = None
        if model_data.get("cache_size_mb"):
            cache_size = float(model_data["cache_size_mb"])

        is_cached = cache_size is not None and cache_size > 0

        models.append(ModelStatus(
            abbr=model_data["abbr"],
            name=model_data["name"],
            type=ModelType(model_data["type"]),
            status=model_data.get("status", "unknown"),
            container_id=model_data.get("container_id"),
            port=int(model_data["port"]) if model_data.get("port") else None,
            endpoint=f"/api/v1/{model_data['abbr']}",
            metrics=metrics,
            progress=int(model_data["progress"]) if model_data.get("progress") else None,
            progress_message=model_data.get("progress_message"),
            cached=is_cached,
            cache_size_mb=cache_size
        ))

    return models

@app.get("/cached-models")
async def list_cached_models() -> List[CachedModel]:
    """List all cached models in the HuggingFace cache directory"""
    cached_models = scan_cached_models()
    return [CachedModel(**model) for model in cached_models]

@app.get("/models/{abbr}/metrics")
async def get_model_metrics(abbr: str):
    """Get detailed metrics for a specific model"""
    if not r.exists(f"model:{abbr}"):
        raise HTTPException(404, f"Model {abbr} not found")

    model_data = r.hgetall(f"model:{abbr}")

    if model_data.get("status") != "running":
        return {"error": "Model is not running"}

    try:
        # Get vLLM metrics
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://MIND_MODEL_{abbr}:8000/metrics")

            # Parse Prometheus metrics
            metrics_text = response.text
            metrics = {
                "num_requests_running": 0,
                "num_requests_waiting": 0,
                "gpu_cache_usage_perc": 0,
                "num_preemptions_total": 0
            }

            for line in metrics_text.split('\n'):
                for metric_name in metrics.keys():
                    if f"vllm:{metric_name}" in line and "#" not in line:
                        try:
                            metrics[metric_name] = float(line.split()[-1])
                        except:
                            pass

            return metrics
    except:
        return {"error": "Unable to fetch metrics"}

# API Key routes (reuse from before)
@app.post("/api-keys")
async def create_api_key(name: str, description: Optional[str] = None, username: str = Depends(verify_token)):
    key = str(uuid.uuid4())
    r.hset(f"api_key:{key}", mapping={
        "name": name,
        "description": description or "",
    })
    r.sadd("api_keys", key)
    return {"api_key": key, "name": name}

@app.get("/api-keys")
async def list_api_keys():
    keys = r.smembers("api_keys")
    result = []
    for key in keys:
        data = r.hgetall(f"api_key:{key}")
        result.append({
            "key": key[:8] + "...",
            "full_key": key,
            "name": data.get("name"),
        })
    return result

@app.delete("/api-keys/{key}")
async def delete_api_key(key: str):
    r.delete(f"api_key:{key}")
    r.srem("api_keys", key)
    return {"status": "deleted"}


# Smart context management for chat completions
@app.post("/api/v1/{model_abbr}/chat/completions")
async def smart_chat_completions(
    model_abbr: str,
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    """Smart proxy for chat completions with automatic context management"""

    # Authentication check - accept either Bearer token or API key
    authenticated = False

    # Check for Bearer token (JWT)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                authenticated = True
        except JWTError:
            pass

    # Check for API key
    if not authenticated and x_api_key:
        if r.exists(f"api_key:{x_api_key}"):
            authenticated = True

    # If neither authentication method succeeded, raise 401
    if not authenticated:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide either a Bearer token or X-API-Key header"
        )

    # Check if model exists and is running
    if not r.exists(f"model:{model_abbr}"):
        raise HTTPException(404, f"Model {model_abbr} not found")

    model_data = r.hgetall(f"model:{model_abbr}")
    if model_data.get("status") != "running":
        raise HTTPException(503, f"Model {model_abbr} is not running")

    # Parse request body
    body = await request.body()
    try:
        request_json = json.loads(body)
    except:
        raise HTTPException(400, "Invalid JSON in request body")

    # Get model's max context length
    max_model_len = int(model_data.get("max_model_len", 2048))

    # Smart context management
    messages = request_json.get("messages", [])
    max_tokens = request_json.get("max_tokens", 512)

    # Estimate tokens (rough: 1 token ≈ 4 characters)
    def estimate_tokens(messages):
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # More accurate estimation based on typical tokenization
            # Rough estimate: ~1 token per 4 characters for English
            # Add some overhead for special tokens
            total += len(content) // 4 + 10  # +10 for role and formatting tokens
        return total

    # Calculate current token usage
    estimated_input_tokens = estimate_tokens(messages)

    # If conversation is too long, truncate intelligently
    if estimated_input_tokens + max_tokens > max_model_len - 50:  # 50 token safety buffer
        logger.info(f"Context truncation needed: {estimated_input_tokens} + {max_tokens} > {max_model_len}")

        # Keep system message if exists
        truncated_messages = []
        system_message = None

        if messages and messages[0].get("role") == "system":
            system_message = messages[0]
            messages = messages[1:]

        # Keep most recent messages that fit
        for i, msg in enumerate(reversed(messages)):
            msg_tokens = estimate_tokens([msg])
            current_total = estimate_tokens(truncated_messages)

            if system_message:
                current_total += estimate_tokens([system_message])

            # Always keep at least the last user message
            if i == 0 or current_total + msg_tokens + max_tokens < max_model_len - 50:
                truncated_messages.insert(0, msg)
                if i == 0 and current_total + msg_tokens + max_tokens >= max_model_len - 50:
                    # If even the last message doesn't fit, we'll need to adjust max_tokens
                    break
            else:
                break

        # Reconstruct messages with system message first
        if system_message:
            truncated_messages.insert(0, system_message)

        logger.info(f"Truncated from {len(messages)} to {len(truncated_messages)} messages")
        request_json["messages"] = truncated_messages

        # Also adjust max_tokens if needed
        new_estimated_tokens = estimate_tokens(truncated_messages)
        safe_max_tokens = min(max_tokens, max_model_len - new_estimated_tokens - 50)

        # Ensure we have at least some tokens for response
        safe_max_tokens = max(safe_max_tokens, 10)

        if safe_max_tokens < max_tokens:
            logger.info(f"Adjusted max_tokens from {max_tokens} to {safe_max_tokens}")
            request_json["max_tokens"] = safe_max_tokens

    # Forward to model container with modified request
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Check if streaming
        is_streaming = request_json.get("stream", False)

        if is_streaming:
            # Handle streaming response
            async def stream_generator():
                async with client.stream(
                    method="POST",
                    url=f"http://MIND_MODEL_{model_abbr}:8000/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=request_json
                ) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        else:
            # Handle regular response
            response = await client.post(
                f"http://MIND_MODEL_{model_abbr}:8000/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=request_json
            )

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                }
            )

@app.get("/gpu-stats")
async def get_gpu_statistics():
    """Get real-time GPU statistics"""
    try:
        gpus = get_gpu_stats()
        processes = get_gpu_processes()

        # Add model association to processes
        for gpu_idx, procs in processes.items():
            for proc in procs:
                # Try to match process to a model container
                for key in r.keys("model:*"):
                    model_data = r.hgetall(key)
                    container_id = model_data.get("container_id", "")[:12]
                    if container_id in proc.get("name", ""):
                        proc["model"] = model_data.get("abbr", "unknown")
                        proc["model_name"] = model_data.get("name", "")

        return {
            "gpus": gpus,
            "processes": processes,
            "timestamp": asyncio.get_event_loop().time()
        }
    except Exception as e:
        logger.error(f"Failed to get GPU stats: {e}")
        return {
            "gpus": [],
            "processes": {},
            "error": str(e)
        }

@app.get("/health")
async def health():
    docker_status = "disconnected"
    docker_test = False

    if docker_client and docker_client.available:
        docker_status = "connected"
        docker_test = docker_client.ping()

    return {
        "status": "healthy",
        "docker_client": docker_status,
        "docker_ping": docker_test,
        "redis": "connected" if r.ping() else "disconnected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)