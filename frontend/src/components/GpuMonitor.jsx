import React, { useState, useEffect } from 'react';
import {
  Cpu,
  HardDrive,
  Thermometer,
  Activity,
  Server,
  Zap,
  AlertCircle,
  TrendingUp
} from 'lucide-react';

const GpuMonitor = ({ apiUrl }) => {
  const [gpuStats, setGpuStats] = useState({ gpus: [], processes: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchGpuStats();
    const interval = setInterval(fetchGpuStats, 2000); // Update every 2 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchGpuStats = async () => {
    try {
      const response = await fetch(`${apiUrl}/gpu-stats`);
      if (response.ok) {
        const data = await response.json();
        setGpuStats(data);
        setError(null);
      } else {
        setError('Failed to fetch GPU stats');
      }
      setLoading(false);
    } catch (err) {
      setError('Error connecting to server');
      setLoading(false);
    }
  };

  const getUtilizationColor = (percent) => {
    if (percent > 90) return 'text-red-400';
    if (percent > 70) return 'text-yellow-400';
    if (percent > 50) return 'text-blue-400';
    return 'text-green-400';
  };

  const getMemoryColor = (percent) => {
    if (percent > 90) return 'bg-gradient-to-r from-red-500 to-red-600';
    if (percent > 70) return 'bg-gradient-to-r from-yellow-500 to-orange-500';
    if (percent > 50) return 'bg-gradient-to-r from-blue-500 to-indigo-500';
    return 'bg-gradient-to-r from-green-500 to-emerald-500';
  };

  const getTemperatureColor = (temp) => {
    if (temp > 80) return 'text-red-400';
    if (temp > 70) return 'text-orange-400';
    if (temp > 60) return 'text-yellow-400';
    return 'text-green-400';
  };

  if (loading && gpuStats.gpus.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white/60">Loading GPU statistics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card-glass p-6">
        <div className="flex items-center space-x-3 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* GPU Cards */}
      {gpuStats.gpus.map((gpu, index) => (
        <div key={index} className="card-glass p-6">
          {/* GPU Header */}
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/30 to-purple-500/30 flex items-center justify-center">
                <Cpu className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-white font-semibold text-lg">GPU {gpu.index}</h3>
                <p className="text-white/60 text-sm">{gpu.name}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <div className="text-xs text-white/60">Temperature</div>
                <div className={`font-semibold ${getTemperatureColor(gpu.temperature_celsius)}`}>
                  {gpu.temperature_celsius}°C
                </div>
              </div>
              <Thermometer className={`w-5 h-5 ${getTemperatureColor(gpu.temperature_celsius)}`} />
            </div>
          </div>

          {/* Memory Usage */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <HardDrive className="w-4 h-4 text-white/60" />
                <span className="text-sm font-medium text-white">VRAM Usage</span>
              </div>
              <span className="text-sm text-white/80">
                {(gpu.memory_used_mb / 1024).toFixed(1)} / {(gpu.memory_total_mb / 1024).toFixed(1)} GB
                <span className="text-white/60 ml-2">({gpu.memory_used_percent}%)</span>
              </span>
            </div>
            <div className="progress-glass h-3">
              <div
                className={`h-full rounded-full transition-all duration-500 ${getMemoryColor(gpu.memory_used_percent)}`}
                style={{ width: `${gpu.memory_used_percent}%` }}
              >
                <div className="h-full bg-white/20 animate-pulse rounded-full" />
              </div>
            </div>
          </div>

          {/* GPU Utilization */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <Activity className="w-4 h-4 text-white/60" />
                <span className="text-sm font-medium text-white">GPU Utilization</span>
              </div>
              <span className={`text-sm font-semibold ${getUtilizationColor(gpu.utilization_percent)}`}>
                {gpu.utilization_percent}%
              </span>
            </div>
            <div className="progress-glass h-2">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-500"
                style={{ width: `${gpu.utilization_percent}%` }}
              />
            </div>
          </div>

          {/* Running Processes */}
          {gpuStats.processes[gpu.index] && gpuStats.processes[gpu.index].length > 0 && (
            <div>
              <div className="flex items-center space-x-2 mb-3">
                <Server className="w-4 h-4 text-white/60" />
                <span className="text-sm font-medium text-white">Active Models</span>
              </div>
              <div className="space-y-2">
                {gpuStats.processes[gpu.index].map((proc, i) => (
                  <div key={i} className="bg-white/5 rounded-lg p-3 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Zap className="w-4 h-4 text-yellow-400" />
                      <div>
                        <div className="text-sm font-medium text-white">
                          {proc.model || proc.name}
                        </div>
                        <div className="text-xs text-white/60">
                          PID: {proc.pid}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-white">
                        {(proc.memory_mb / 1024).toFixed(1)} GB
                      </div>
                      <div className="text-xs text-white/60">VRAM</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stats Grid */}
          <div className="grid grid-cols-3 gap-4 mt-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-white">
                {(gpu.memory_free_mb / 1024).toFixed(1)}
              </div>
              <div className="text-xs text-white/60">GB Free</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-white">
                {gpu.utilization_percent}
              </div>
              <div className="text-xs text-white/60">% Active</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-white">
                {gpuStats.processes[gpu.index]?.length || 0}
              </div>
              <div className="text-xs text-white/60">Models</div>
            </div>
          </div>
        </div>
      ))}

      {/* Multi-GPU Summary */}
      {gpuStats.gpus.length > 1 && (
        <div className="card-glass p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center space-x-2">
            <TrendingUp className="w-5 h-5" />
            <span>System Overview</span>
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-xs text-white/60 mb-1">Total VRAM</div>
              <div className="text-xl font-bold text-white">
                {(gpuStats.gpus.reduce((sum, gpu) => sum + gpu.memory_total_mb, 0) / 1024).toFixed(0)} GB
              </div>
            </div>
            <div>
              <div className="text-xs text-white/60 mb-1">Used VRAM</div>
              <div className="text-xl font-bold text-white">
                {(gpuStats.gpus.reduce((sum, gpu) => sum + gpu.memory_used_mb, 0) / 1024).toFixed(1)} GB
              </div>
            </div>
            <div>
              <div className="text-xs text-white/60 mb-1">Available VRAM</div>
              <div className="text-xl font-bold text-green-400">
                {(gpuStats.gpus.reduce((sum, gpu) => sum + gpu.memory_free_mb, 0) / 1024).toFixed(1)} GB
              </div>
            </div>
            <div>
              <div className="text-xs text-white/60 mb-1">Active Models</div>
              <div className="text-xl font-bold text-white">
                {Object.values(gpuStats.processes).reduce((sum, procs) => sum + procs.length, 0)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GpuMonitor;