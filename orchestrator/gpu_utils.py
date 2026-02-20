"""
GPU management utilities for the orchestrator.
"""
import subprocess
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_gpu_stats() -> List[Dict[str, Any]]:
    """Get GPU stats - try multiple methods"""
    try:
        # Try to run nvidia-smi directly
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,memory.free,utilization.gpu,temperature.gpu",
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
        logger.debug(f"Could not get GPU info via nvidia-smi: {e}")

    # Fallback: Return hardcoded GPU info for known system (2x RTX A6000)
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


def get_gpu_processes() -> Dict[int, List[Dict[str, Any]]]:
    """Get processes running on each GPU"""
    gpu_processes = {}
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 4:
                    # Parse GPU index from UUID or use a mapping
                    gpu_idx = 0  # Simplified - would need UUID mapping
                    if gpu_idx not in gpu_processes:
                        gpu_processes[gpu_idx] = []

                    gpu_processes[gpu_idx].append({
                        "pid": int(parts[1]),
                        "name": parts[2],
                        "memory_mb": float(parts[3])
                    })
    except Exception as e:
        logger.debug(f"Could not get GPU processes: {e}")

    return gpu_processes


def get_available_gpu(redis_client) -> int:
    """
    Get the least loaded available GPU based on memory usage and assigned models.

    Args:
        redis_client: Redis connection object

    Returns:
        GPU index to use for deployment
    """
    try:
        # Get current GPU usage
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,memory.used', '--format=csv,nounits,noheader'],
            capture_output=True, text=True
        )

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
        for key in redis_client.keys("model:*"):
            model_data = redis_client.hgetall(key)
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