import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import ModelManager from './components/ModelManager';
import ApiKeyManager from './components/ApiKeyManager';
import ChatPlayground from './components/ChatPlayground';
import Login from './components/Login';
import { AuthProvider, useAuth } from './context/AuthContext';
import './styles/app.css';
import './index.css';

const API_URL = import.meta.env.VITE_API_URL || '/orchestrator';

function AppContent() {
  const [models, setModels] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(false); // Don't block initial render
  const [dataLoading, setDataLoading] = useState(true); // Track data loading separately
  const [activeView, setActiveView] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { isAuthenticated, login, logout, fetchWithAuth, loading: authLoading } = useAuth();

  // Set dark mode as default
  useEffect(() => {
    document.documentElement.style.backgroundColor = '#030712';
    document.body.style.backgroundColor = '#030712';
  }, []);

  // Fetch data asynchronously without blocking (only when authenticated)
  useEffect(() => {
    if (isAuthenticated) {
      // Fetch data in background
      Promise.all([
        fetchModels(),
        fetchApiKeys()
      ]).finally(() => {
        setDataLoading(false);
      });
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const hasDeployingModels = models.some(m => m.status === 'deploying');
    const pollInterval = hasDeployingModels ? 1000 : 5000;

    const interval = setInterval(fetchModels, pollInterval);
    return () => clearInterval(interval);
  }, [models, isAuthenticated]);

  const fetchModels = async () => {
    try {
      // Models endpoint is public, no auth needed
      const res = await fetch(`${API_URL}/models`);
      const data = await res.json();
      setModels(data);
    } catch (error) {
      console.error('Failed to fetch models:', error);
    }
  };

  const fetchApiKeys = async () => {
    try {
      const res = await fetchWithAuth(`${API_URL}/api-keys`);
      const data = await res.json();
      setApiKeys(data);
    } catch (error) {
      console.error('Failed to fetch API keys:', error);
    }
  };

  // Page titles and descriptions
  const pageInfo = {
    dashboard: {
      title: 'Dashboard',
      subtitle: 'System overview and key metrics'
    },
    'all-models': {
      title: 'Model Library',
      subtitle: 'Browse and deploy AI models'
    },
    deployed: {
      title: 'Active Models',
      subtitle: 'Currently running model instances'
    },
    llm: {
      title: 'Language Models',
      subtitle: 'Large language models for text generation'
    },
    embedding: {
      title: 'Embedding Models',
      subtitle: 'Vector embedding models for semantic search'
    },
    quantized: {
      title: 'Quantized Models',
      subtitle: 'Optimized models for faster inference'
    },
    chat: {
      title: 'Chat Playground',
      subtitle: 'Test and interact with deployed models'
    },
    'api-keys': {
      title: 'API Keys',
      subtitle: 'Manage authentication and access'
    }
  };

  const currentPage = pageInfo[activeView] || pageInfo.dashboard;

  // Show loading spinner while checking auth
  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <Login onLogin={login} />;
  }

  return (
    <div className="app-wrapper">
      {/* Logout button */}
      <button
        onClick={logout}
        className="fixed top-4 right-4 z-50 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        Logout
      </button>

      {/* Sidebar */}
      <Sidebar
        activeView={activeView}
        setActiveView={setActiveView}
        models={models}
        onCollapseChange={setSidebarCollapsed}
      />

      {/* Main Content Area */}
      <main className={`app-main ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        {/* Page Content */}
        <div className="app-content animate-fade-in pt-6">
          {/* Dashboard */}
          {activeView === 'dashboard' && (
            <Dashboard models={models} loading={loading} />
          )}

          {/* Model Library */}
          {activeView === 'all-models' && (
            <div className="space-y-6">
              <ModelManager
                models={models}
                onModelDeployed={fetchModels}
                onModelStopped={fetchModels}
                apiUrl={API_URL}
              />
            </div>
          )}

          {/* Active Models */}
          {activeView === 'deployed' && (
            <div className="space-y-6">
              <ModelManager
                models={models.filter(m => m.status === 'running' || m.status === 'deploying')}
                onModelDeployed={fetchModels}
                onModelStopped={fetchModels}
                apiUrl={API_URL}
                filterType="deployed"
              />
            </div>
          )}

          {/* LLM Models */}
          {activeView === 'llm' && (
            <div className="space-y-6">
              <ModelManager
                models={models.filter(m => m.type === 'llm')}
                onModelDeployed={fetchModels}
                onModelStopped={fetchModels}
                apiUrl={API_URL}
                filterType="llm"
              />
            </div>
          )}

          {/* Embedding Models */}
          {activeView === 'embedding' && (
            <div className="space-y-6">
              <ModelManager
                models={models.filter(m => m.type === 'embedding')}
                onModelDeployed={fetchModels}
                onModelStopped={fetchModels}
                apiUrl={API_URL}
                filterType="embedding"
              />
            </div>
          )}

          {/* Quantized Models */}
          {activeView === 'quantized' && (
            <div className="space-y-6">
              <ModelManager
                models={models.filter(m => m.quantization === 'awq' || m.quantization === 'gptq')}
                onModelDeployed={fetchModels}
                onModelStopped={fetchModels}
                apiUrl={API_URL}
                filterType="quantized"
              />
            </div>
          )}

          {/* Chat Playground */}
          {activeView === 'chat' && (
            <div className="space-y-6">
              <ChatPlayground models={models} apiUrl={API_URL} />
            </div>
          )}


          {/* API Keys */}
          {activeView === 'api-keys' && (
            <div className="space-y-6">
              <ApiKeyManager
                apiKeys={apiKeys}
                onKeysUpdated={fetchApiKeys}
                apiUrl={API_URL}
                fetchWithAuth={fetchWithAuth}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// Main App component with AuthProvider
function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;