"""
Model definitions and model management logic.
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import os
import glob
import logging
from config import HF_CACHE_DIR, MODELS_CONFIG

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    LLM = "llm"
    EMBEDDING = "embedding"
    RERANKER = "reranker"
    VISION = "vision"


class ModelConfig(BaseModel):
    """Configuration for deploying a model"""
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
    """Status information for a deployed model"""
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
    gpu_device: Optional[int] = None


class CachedModel(BaseModel):
    """Information about a cached model in the HuggingFace cache"""
    name: str
    cache_path: str
    size_mb: float
    cached: bool = True


def get_model_config_from_json(abbr: str, name: str = None) -> Optional[Dict[str, Any]]:
    """
    Get model configuration from models.json

    Args:
        abbr: Model abbreviation
        name: Optional full model name

    Returns:
        Model configuration dict or None if not found
    """
    return MODELS_CONFIG['models'].get(abbr) or (
        MODELS_CONFIG['models'].get(name) if name else None
    )


def get_model_settings(config: ModelConfig) -> Dict[str, Any]:
    """
    Get optimized settings for a model based on models.json or smart defaults.

    Args:
        config: ModelConfig object

    Returns:
        Dictionary with optimized settings
    """
    # Try to load from models.json first
    model_json_config = get_model_config_from_json(config.abbr, config.name)

    if model_json_config:
        recommended = model_json_config.get('recommended_settings', {})
        return {
            'gpu_memory_utilization': recommended.get('gpu_memory_utilization', config.gpu_memory_utilization),
            'max_model_len': model_json_config.get('max_model_len', config.max_model_len),
            'max_num_seqs': recommended.get('max_num_seqs', config.max_num_seqs),
            'quantization': model_json_config.get('quantization', config.quantization),
            'type': model_json_config.get('type', config.type.value)
        }

    # Fallback to smart defaults based on model characteristics
    settings = {
        'gpu_memory_utilization': config.gpu_memory_utilization,
        'max_model_len': config.max_model_len,
        'max_num_seqs': config.max_num_seqs,
        'quantization': config.quantization,
        'type': config.type.value
    }

    # Optimize based on quantization
    if config.quantization in ["awq", "gptq"]:
        settings['gpu_memory_utilization'] = 0.25
        settings['max_model_len'] = 2048
        settings['max_num_seqs'] = 256

    # Optimize based on model type
    elif config.type == ModelType.EMBEDDING:
        settings['gpu_memory_utilization'] = 0.05
        settings['max_model_len'] = 512
        settings['max_num_seqs'] = 1024

    # Optimize based on model size (if detectable from name)
    elif "7b" in config.name.lower():
        settings['gpu_memory_utilization'] = 0.5
        settings['max_model_len'] = 4096
        settings['max_num_seqs'] = 128
    elif "13b" in config.name.lower():
        settings['gpu_memory_utilization'] = 0.7
        settings['max_model_len'] = 4096
        settings['max_num_seqs'] = 64

    return settings


def scan_cached_models() -> List[CachedModel]:
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
                                cached_models.append(CachedModel(
                                    name=model_name,
                                    cache_path=model_dir,
                                    size_mb=round(size / (1024 * 1024), 2),
                                    cached=True
                                ))
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


def get_directory_size(path: str) -> int:
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


def build_vllm_command(config: ModelConfig, settings: Dict[str, Any], port: int = 8000) -> List[str]:
    """
    Build vLLM command line arguments for a model.

    Args:
        config: ModelConfig object
        settings: Optimized settings dictionary
        port: Port to run the model on

    Returns:
        List of command line arguments
    """
    cmd = [
        "--model", config.name,
        "--served-model-name", config.abbr,
        "--max-model-len", str(settings['max_model_len']),
        "--gpu-memory-utilization", str(settings['gpu_memory_utilization']),
        "--max-num-seqs", str(settings['max_num_seqs']),
        "--port", str(port),
        "--host", "0.0.0.0",
        "--download-dir", HF_CACHE_DIR
    ]

    # Add quantization if specified
    if settings.get('quantization'):
        cmd.extend(["--quantization", settings['quantization']])

    # Determine if we should use eager mode (faster loading for small/quantized models)
    # NOTE: Embedding models work fine without special flags (based on working containers)
    use_eager = False
    if settings.get('quantization') in ["awq", "gptq"]:
        use_eager = True
    elif "1.5b" in config.name.lower() or "3b" in config.name.lower():
        use_eager = True

    if use_eager:
        cmd.extend(["--enforce-eager"])

    # Only add prefix caching and chunked prefill for LLM models (not embedding models)
    # This should be independent of eager mode
    if config.type == ModelType.LLM and not use_eager:
        cmd.extend([
            "--enable-prefix-caching",
            "--enable-chunked-prefill"
        ])

    # Add chat template for Llama models
    if "llama" in config.name.lower():
        cmd.extend([
            "--chat-template",
            "{% if messages[0]['role'] == 'system' %}{% set loop_messages = messages[1:] %}{% set system_message = messages[0]['content'] %}{% elif false == true %}{% set loop_messages = messages %}{% set system_message = 'You are a helpful assistant.' %}{% else %}{% set loop_messages = messages %}{% set system_message = false %}{% endif %}{% for message in loop_messages %}{% if loop.index0 == 0 and system_message != false %}{{ '<|im_start|>system\\n' + system_message + '<|im_end|>\\n' }}{% endif %}{{ '<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>' + '\\n' }}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\\n' }}{% endif %}"
        ])

    return cmd