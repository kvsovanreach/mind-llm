import React from 'react';
import {
  Play,
  Square,
  MoreVertical,
  Cpu,
  MemoryStick,
  Activity,
  Download,
  Clock,
  Zap,
  Circle
} from 'lucide-react';

const ModelCard = ({ model, onDeploy, onStop, onDelete, isDeploying = false }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'running':
        return 'badge-success';
      case 'deploying':
        return 'badge-warning';
      case 'stopped':
        return 'badge-error';
      default:
        return 'badge-glass';
    }
  };

  const getModelIcon = () => {
    const icons = ['🤖', '🧠', '⚡', '🎯', '🚀', '💫'];
    const index = model.abbr.charCodeAt(0) % icons.length;
    return icons[index];
  };

  const isQuantized = model.quantization === 'awq' || model.quantization === 'gptq';

  return (
    <div className="card-glass p-6 relative group">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/30 to-pink-500/30 flex items-center justify-center text-2xl">
            {getModelIcon()}
          </div>
          <div>
            <h3 className="text-white font-semibold text-lg">{model.abbr}</h3>
            <p className="text-white/60 text-sm">{model.description}</p>
          </div>
        </div>
        <button className="opacity-0 group-hover:opacity-100 transition-opacity">
          <MoreVertical className="w-5 h-5 text-white/60 hover:text-white" />
        </button>
      </div>

      {/* Status Badge */}
      <div className="flex items-center space-x-2 mb-4">
        <span className={`badge-glass ${getStatusColor(model.status)} flex items-center space-x-1`}>
          <Circle className="w-2 h-2 fill-current" />
          <span>{model.status}</span>
        </span>
        {isQuantized && (
          <span className="badge-glass badge-primary flex items-center space-x-1">
            <Zap className="w-3 h-3" />
            <span>{model.quantization?.toUpperCase()}</span>
          </span>
        )}
        {model.cached && (
          <span className="badge-glass badge-success flex items-center space-x-1">
            <Download className="w-3 h-3" />
            <span>Cached</span>
          </span>
        )}
      </div>

      {/* Model Info */}
      <div className="space-y-3 mb-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/60">Model Size</span>
          <span className="text-white font-medium">
            {model.cache_size_mb ? `${(model.cache_size_mb / 1024).toFixed(1)} GB` : 'N/A'}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/60">Max Length</span>
          <span className="text-white font-medium">{model.max_model_len || '4096'}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/60">Port</span>
          <span className="text-white font-medium">{model.port || 'N/A'}</span>
        </div>
      </div>

      {/* Progress Bar (if deploying) */}
      {model.status === 'deploying' && model.progress !== undefined && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-white/60">{model.progress_message || 'Deploying...'}</span>
            <span className="text-white/80">{model.progress}%</span>
          </div>
          <div className="progress-glass">
            <div className="progress-bar-glass" style={{ width: `${model.progress}%` }}></div>
          </div>
        </div>
      )}

      {/* Metrics (if running) */}
      {model.metrics && model.status === 'running' && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-white/5 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-1">
              <Cpu className="w-4 h-4 text-blue-400" />
              <span className="text-xs text-white/60">CPU</span>
            </div>
            <span className="text-white font-medium">{model.metrics.cpu_usage}%</span>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-1">
              <MemoryStick className="w-4 h-4 text-green-400" />
              <span className="text-xs text-white/60">Memory</span>
            </div>
            <span className="text-white font-medium">{model.metrics.memory_gb} GB</span>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex space-x-2">
        {model.status === 'stopped' ? (
          <button
            onClick={() => onDeploy(model)}
            disabled={isDeploying}
            className="btn-glass btn-glass-primary flex-1 flex items-center justify-center space-x-2"
          >
            <Play className="w-4 h-4" />
            <span>Deploy</span>
          </button>
        ) : model.status === 'running' ? (
          <>
            <button
              onClick={() => onStop(model.abbr)}
              className="btn-glass flex-1 flex items-center justify-center space-x-2"
            >
              <Square className="w-4 h-4" />
              <span>Stop</span>
            </button>
            <button className="btn-glass px-4">
              <Activity className="w-4 h-4" />
            </button>
          </>
        ) : model.status === 'deploying' ? (
          <button disabled className="btn-glass flex-1 flex items-center justify-center space-x-2 opacity-50">
            <Clock className="w-4 h-4 animate-spin" />
            <span>Deploying...</span>
          </button>
        ) : null}
      </div>

      {/* Endpoint URL */}
      {model.status === 'running' && (
        <div className="mt-4 p-3 bg-white/5 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs text-white/60">Endpoint</span>
            <code className="text-xs text-blue-400">{model.endpoint}</code>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelCard;