import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Play,
  Square,
  Cpu,
  HardDrive,
  Activity,
  Loader2,
  Server,
  Copy,
  AlertCircle,
  Trash2,
  Power,
  PowerOff,
  CheckCircle,
  Clock,
  ChevronDown,
  Settings,
  Info,
  Zap
} from 'lucide-react';
import modelConfigs from '../models.json';

const ModelManager = ({ models, onModelDeployed, onModelStopped, apiUrl, filterType }) => {
  const { fetchWithAuth, getAuthHeaders } = useAuth();
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedGpu, setSelectedGpu] = useState(0);
  const [gpuStats, setGpuStats] = useState({ gpus: [] });
  const [deploying, setDeploying] = useState(false);
  const [stoppingModel, setStoppingModel] = useState(null);
  const [startingModel, setStartingModel] = useState(null);
  const [deletingModel, setDeletingModel] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);

  // Filtering and pagination states
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(6);

  const predefinedModels = modelConfigs.predefined_models;

  // Fetch GPU stats
  useEffect(() => {
    const fetchGpuStats = async () => {
      try {
        const response = await fetch(`${apiUrl}/gpu-stats`);
        if (response.ok) {
          const data = await response.json();
          setGpuStats(data);
        }
      } catch (error) {
        console.error('Failed to fetch GPU stats:', error);
      }
    };

    fetchGpuStats();
    const interval = setInterval(fetchGpuStats, 5000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  const handleDeploy = async () => {
    if (!selectedModel) return;

    const modelConfig = predefinedModels.find(m => m.abbr === selectedModel);
    if (!modelConfig) return;

    setDeploying(true);
    try {
      const response = await fetchWithAuth(`${apiUrl}/models/deploy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: modelConfig.name,
          abbr: modelConfig.abbr,
          type: modelConfig.type,
          quantization: modelConfig.quantization,
          max_model_len: modelConfig.max_model_len,
          gpu_memory_utilization: modelConfig.recommended_settings?.gpu_memory_utilization || 0.9,
          max_num_seqs: modelConfig.recommended_settings?.max_num_seqs || 256,
          gpu_device: selectedGpu
        })
      });

      if (response.ok) {
        setSelectedModel('');
        onModelDeployed();
      }
    } catch (error) {
      console.error('Failed to deploy model:', error);
    } finally {
      setDeploying(false);
    }
  };

  const handleStop = async (abbr) => {
    setStoppingModel(abbr);
    try {
      const response = await fetchWithAuth(`${apiUrl}/models/${abbr}/stop`, {
        method: 'POST'
      });

      if (response.ok) {
        onModelStopped();
      }
    } catch (error) {
      console.error('Failed to stop model:', error);
    } finally {
      setStoppingModel(null);
    }
  };

  const handleStart = async (abbr) => {
    setStartingModel(abbr);
    try {
      const response = await fetchWithAuth(`${apiUrl}/models/${abbr}/start`, {
        method: 'POST'
      });

      if (response.ok) {
        onModelDeployed();
      }
    } catch (error) {
      console.error('Failed to start model:', error);
    } finally {
      setStartingModel(null);
    }
  };

  const handleDelete = async (abbr) => {
    setDeletingModel(abbr);
    try {
      const response = await fetch(`${apiUrl}/models/${abbr}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        onModelStopped();
        setShowDeleteConfirm(null);
      }
    } catch (error) {
      console.error('Failed to delete model:', error);
    } finally {
      setDeletingModel(null);
    }
  };

  const copyEndpoint = (endpoint) => {
    const fullUrl = `${window.location.origin}${endpoint}`;
    navigator.clipboard.writeText(fullUrl);
  };

  // Filter out already deployed models
  const availableModels = predefinedModels.filter(
    pm => !models.some(m => m.abbr === pm.abbr)
  );

  // Apply filters
  let filteredModels = [...models];

  // Search filter
  if (searchQuery) {
    filteredModels = filteredModels.filter(m =>
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.abbr.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }

  // Status filter
  if (statusFilter !== 'all') {
    filteredModels = filteredModels.filter(m => m.status === statusFilter);
  }

  // Type filter
  if (typeFilter !== 'all') {
    filteredModels = filteredModels.filter(m => m.type === typeFilter);
  }

  // Pagination
  const totalPages = Math.ceil(filteredModels.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedModels = filteredModels.slice(startIndex, endIndex);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, typeFilter]);

  const ModelCard = ({ model }) => {
    const isRunning = model.status === 'running';
    const isStopped = model.status === 'stopped';
    const isDeploying = model.status === 'deploying';
    const isError = model.status === 'error';

    return (
      <div className="card">
        <div className="card-body">
          {/* Model Header */}
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-heading-4 mb-1">{model.name}</h3>
              <div className="flex items-center gap-3">
                <span className="text-small">{model.abbr}</span>
                <span className={`badge ${
                  model.type === 'llm' ? 'badge-primary' :
                  model.type === 'embedding' ? 'badge-info' :
                  'badge-warning'
                }`}>
                  {model.type}
                </span>
                <span className={`badge ${
                  isRunning ? 'badge-success' :
                  isDeploying ? 'badge-warning' :
                  isStopped ? 'badge-secondary' :
                  'badge-danger'
                }`}>
                  {model.status}
                </span>
                {model.gpu_device !== undefined && (
                  <span className="badge badge-info">
                    GPU {model.gpu_device}
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              {isRunning && (
                <button
                  onClick={() => handleStop(model.abbr)}
                  disabled={stoppingModel === model.abbr}
                  className="btn btn-icon btn-ghost"
                  title="Stop model"
                >
                  {stoppingModel === model.abbr ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <Square size={18} />
                  )}
                </button>
              )}
              {isStopped && (
                <button
                  onClick={() => handleStart(model.abbr)}
                  disabled={startingModel === model.abbr}
                  className="btn btn-icon btn-ghost text-green-600"
                  title="Start model"
                >
                  {startingModel === model.abbr ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <Play size={18} />
                  )}
                </button>
              )}
              <button
                onClick={() => setShowDeleteConfirm(model)}
                disabled={deletingModel === model.abbr || isDeploying}
                className="btn btn-icon btn-ghost text-red-600"
                title="Delete model"
              >
                {deletingModel === model.abbr ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Trash2 size={18} />
                )}
              </button>
            </div>
          </div>

          {/* Endpoint */}
          <div className="flex items-center gap-2 p-3 bg-gray-800 rounded-lg mb-4">
            <code className="text-small flex-1 font-mono">{model.endpoint}</code>
            <button
              onClick={() => copyEndpoint(model.endpoint)}
              className="btn btn-icon btn-ghost btn-sm"
            >
              <Copy size={14} />
            </button>
          </div>

          {/* Progress Bar for Deploying */}
          {isDeploying && model.progress !== undefined && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-small">{model.progress_message || 'Deploying...'}</span>
                <span className="text-small font-semibold">{model.progress}%</span>
              </div>
              <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${model.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Error Message */}
          {isError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-small">
              <AlertCircle size={16} />
              <span>{model.progress_message || 'Failed to deploy. Check logs.'}</span>
            </div>
          )}

          {/* Metrics */}
          {model.metrics && isRunning && (
            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <Cpu size={16} className="text-gray-400" />
                <span className="text-small">CPU: {model.metrics.cpu_usage}%</span>
              </div>
              <div className="flex items-center gap-2">
                <HardDrive size={16} className="text-gray-400" />
                <span className="text-small">Memory: {model.metrics.memory_gb}GB</span>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Deploy New Model */}
      {!filterType || filterType === 'all' ? (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Deploy New Model</h3>
            <button
              onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
              className="btn btn-ghost btn-sm"
            >
              <Settings size={14} />
              Advanced
              <ChevronDown size={14} className={`transition-transform ${showAdvancedOptions ? 'rotate-180' : ''}`} />
            </button>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div className="form-group">
                <label className="label">Select Model</label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="input"
                >
                  <option value="">Choose a model...</option>
                  {availableModels.map((model) => (
                    <option key={model.abbr} value={model.abbr}>
                      {model.abbr} - {model.description}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="label">GPU Device</label>
                <select
                  value={selectedGpu}
                  onChange={(e) => setSelectedGpu(parseInt(e.target.value))}
                  className="input"
                >
                  {gpuStats.gpus.length > 0 ? (
                    gpuStats.gpus.map((gpu) => (
                      <option key={gpu.index} value={gpu.index}>
                        GPU {gpu.index}: {gpu.name} ({(gpu.memory_free_mb / 1024).toFixed(1)}GB free)
                      </option>
                    ))
                  ) : (
                    <option value="0">GPU 0 (Default)</option>
                  )}
                </select>
              </div>
            </div>

            {/* GPU Info */}
            {selectedModel && gpuStats.gpus[selectedGpu] && (
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg mb-4">
                <div className="flex items-start gap-2">
                  <Info size={16} className="text-blue-600 dark:text-blue-400 mt-0.5" />
                  <div className="text-small">
                    <p className="font-medium text-blue-900 dark:text-blue-300 mb-1">
                      GPU {selectedGpu} has {(gpuStats.gpus[selectedGpu].memory_free_mb / 1024).toFixed(1)}GB available
                    </p>
                    <p className="text-blue-700 dark:text-blue-400">
                      Current utilization: {gpuStats.gpus[selectedGpu].utilization_percent}%
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Advanced Options */}
            {showAdvancedOptions && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4 p-4 bg-gray-800 rounded-lg">
                <div className="form-group">
                  <label className="label">GPU Memory Utilization</label>
                  <input type="number" className="input" defaultValue="0.9" step="0.1" min="0.1" max="1" />
                </div>
                <div className="form-group">
                  <label className="label">Max Sequences</label>
                  <input type="number" className="input" defaultValue="256" min="1" />
                </div>
              </div>
            )}

            <button
              onClick={handleDeploy}
              disabled={!selectedModel || deploying}
              className="btn btn-primary"
            >
              {deploying ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Deploying...
                </>
              ) : (
                <>
                  <Play size={16} />
                  Deploy Model
                </>
              )}
            </button>
          </div>
        </div>
      ) : null}

      {/* Filters and Search */}
      <div className="card">
        <div className="card-body">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="form-group">
              <input
                type="text"
                placeholder="Search models..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input"
              />
            </div>

            {/* Status Filter */}
            <div className="form-group">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input"
              >
                <option value="all">All Status</option>
                <option value="running">Running</option>
                <option value="stopped">Stopped</option>
                <option value="deploying">Deploying</option>
                <option value="error">Error</option>
              </select>
            </div>

            {/* Type Filter */}
            <div className="form-group">
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="input"
              >
                <option value="all">All Types</option>
                <option value="llm">Language Models</option>
                <option value="embedding">Embeddings</option>
              </select>
            </div>

            {/* Items per page */}
            <div className="form-group">
              <select
                value={itemsPerPage}
                onChange={(e) => setItemsPerPage(Number(e.target.value))}
                className="input"
              >
                <option value="3">3 per page</option>
                <option value="6">6 per page</option>
                <option value="9">9 per page</option>
                <option value="12">12 per page</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Model List */}
      <div className="grid grid-cols-1 gap-4">
        {models.length === 0 ? (
          <div className="card">
            <div className="card-body text-center py-12">
              <Server size={48} className="mx-auto mb-4 text-gray-400" />
              <p className="text-body mb-4">No models deployed yet</p>
              <button
                onClick={() => setActiveView && setActiveView('all-models')}
                className="btn btn-primary mx-auto"
              >
                Deploy Your First Model
              </button>
            </div>
          </div>
        ) : (
          paginatedModels.map((model) => <ModelCard key={model.abbr} model={model} />)
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <p className="text-small">
                Showing {startIndex + 1} to {Math.min(endIndex, filteredModels.length)} of {filteredModels.length} models
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                  className="btn btn-secondary btn-sm"
                >
                  Previous
                </button>
                {[...Array(totalPages)].map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setCurrentPage(i + 1)}
                    className={`btn btn-sm ${
                      currentPage === i + 1 ? 'btn-primary' : 'btn-secondary'
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
                <button
                  onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                  className="btn btn-secondary btn-sm"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card max-w-md w-full animate-scale-in">
            <div className="card-header">
              <h3 className="card-title">Delete Model</h3>
            </div>
            <div className="card-body">
              <p className="text-body mb-4">
                Are you sure you want to delete <strong>{showDeleteConfirm.name}</strong>?
              </p>
              <p className="text-small">
                This will stop the model and remove its configuration. This action cannot be undone.
              </p>
            </div>
            <div className="card-footer">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(showDeleteConfirm.abbr)}
                className="btn btn-danger"
              >
                Delete Model
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelManager;