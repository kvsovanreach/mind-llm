import React from 'react';
import {
  Activity,
  Cpu,
  Clock,
  BarChart3,
  Layers,
  Zap,
  Database,
  ArrowUp,
  ArrowDown
} from 'lucide-react';

const Dashboard = ({ models = [], loading }) => {
  // Calculate stats
  const stats = {
    total: models.length,
    running: models.filter(m => m.status === 'running').length,
    stopped: models.filter(m => m.status === 'stopped').length,
    deploying: models.filter(m => m.status === 'deploying').length,
    error: models.filter(m => m.status === 'error').length,
    llm: models.filter(m => m.type === 'llm').length,
    embedding: models.filter(m => m.type === 'embedding').length,
    quantized: models.filter(m => m.quantization === 'awq' || m.quantization === 'gptq').length
  };

  // Mock performance metrics
  const metrics = {
    requestsPerMin: 1847,
    avgResponse: 127,
    successRate: 99.92,
    totalRequests: '3.2M',
    cpuUsage: 42,
    memoryUsage: 68,
    activeConnections: 284
  };

  const MetricCard = ({ icon: Icon, label, value, change, trend, colorClass }) => (
    <div className="card">
      <div className="mb-4">
        <div className={`p-2.5 rounded-xl ${colorClass} inline-block`}>
          <Icon size={20} />
        </div>
      </div>
      <p className="text-small mb-1">{label}</p>
      <p className="text-heading-3">{value}</p>
      {change && (
        <div className="flex items-center gap-1 mt-2">
          {trend === 'up' ? (
            <ArrowUp size={14} className="text-green-500" />
          ) : (
            <ArrowDown size={14} className="text-red-500" />
          )}
          <span className={`text-tiny font-medium ${
            trend === 'up' ? 'text-green-400' : 'text-red-400'
          }`}>
            {change}% from last period
          </span>
        </div>
      )}
    </div>
  );

  const StatusChart = () => {
    const total = stats.total || 1;
    const runningPercent = Math.round((stats.running / total) * 100);

    return (
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Model Status</h3>
          <span className="badge badge-primary">{stats.total} Total</span>
        </div>
        <div className="card-body">
          <div className="flex items-center justify-center mb-6">
            <div className="relative w-40 h-40">
              <svg className="w-full h-full -rotate-90">
                <circle
                  cx="80"
                  cy="80"
                  r="70"
                  stroke="currentColor"
                  strokeWidth="12"
                  fill="none"
                  className="text-gray-700"
                />
                <circle
                  cx="80"
                  cy="80"
                  r="70"
                  stroke="currentColor"
                  strokeWidth="12"
                  fill="none"
                  strokeDasharray={`${(runningPercent / 100) * 440} 440`}
                  className="text-green-500"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <span className="text-3xl font-bold">{stats.running}</span>
                <span className="text-small">Active</span>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-small">Running</span>
              </div>
              <span className="text-small font-semibold">{stats.running}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-gray-400"></div>
                <span className="text-small">Stopped</span>
              </div>
              <span className="text-small font-semibold">{stats.stopped}</span>
            </div>
            {stats.deploying > 0 && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <span className="text-small">Deploying</span>
                </div>
                <span className="text-small font-semibold">{stats.deploying}</span>
              </div>
            )}
            {stats.error > 0 && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <span className="text-small">Error</span>
                </div>
                <span className="text-small font-semibold">{stats.error}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const SystemHealth = () => (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">System Health</h3>
        <span className="badge badge-success">Healthy</span>
      </div>
      <div className="card-body space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-small">CPU Usage</span>
            <span className="text-small font-semibold">{metrics.cpuUsage}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${metrics.cpuUsage}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-small">Memory Usage</span>
            <span className="text-small font-semibold">{metrics.memoryUsage}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-500 rounded-full transition-all duration-500"
              style={{ width: `${metrics.memoryUsage}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-small">Active Connections</span>
            <span className="text-small font-semibold">{metrics.activeConnections}</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-500"
              style={{ width: '28%' }}
            />
          </div>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-12 h-12 border-3 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-small">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          icon={Layers}
          label="Total Models"
          value={stats.total}
          change={12}
          trend="up"
          colorClass="bg-blue-100 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
        />
        <MetricCard
          icon={Activity}
          label="Active Models"
          value={stats.running}
          change={8}
          trend="up"
          colorClass="bg-green-100 dark:bg-green-900/20 text-green-600 dark:text-green-400"
        />
        <MetricCard
          icon={BarChart3}
          label="Total Requests"
          value={metrics.totalRequests}
          change={23}
          trend="up"
          colorClass="bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400"
        />
        <MetricCard
          icon={Clock}
          label="Avg Response"
          value={`${metrics.avgResponse}ms`}
          change={5}
          trend="down"
          colorClass="bg-orange-100 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400"
        />
      </div>

      {/* Model Type Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card bg-gradient-to-br from-blue-500 to-blue-600 text-white border-0">
          <div className="card-body">
            <div className="flex items-center justify-between mb-4">
              <Cpu size={32} className="opacity-80" />
              <span className="text-3xl font-bold">{stats.llm}</span>
            </div>
            <h4 className="text-lg font-semibold mb-1">Language Models</h4>
            <p className="text-sm opacity-90">LLMs for text generation</p>
          </div>
        </div>
        <div className="card bg-gradient-to-br from-purple-500 to-purple-600 text-white border-0">
          <div className="card-body">
            <div className="flex items-center justify-between mb-4">
              <Database size={32} className="opacity-80" />
              <span className="text-3xl font-bold">{stats.embedding}</span>
            </div>
            <h4 className="text-lg font-semibold mb-1">Embeddings</h4>
            <p className="text-sm opacity-90">Vector models for search</p>
          </div>
        </div>
        <div className="card bg-gradient-to-br from-orange-500 to-orange-600 text-white border-0">
          <div className="card-body">
            <div className="flex items-center justify-between mb-4">
              <Zap size={32} className="opacity-80" />
              <span className="text-3xl font-bold">{stats.quantized}</span>
            </div>
            <h4 className="text-lg font-semibold mb-1">Quantized</h4>
            <p className="text-sm opacity-90">Optimized for speed</p>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SystemHealth />
        <StatusChart />
      </div>
    </div>
  );
};

export default Dashboard;