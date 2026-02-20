import React, { useState, useEffect } from 'react';
import {
  LayoutGrid,
  Layers,
  Cpu,
  Database,
  Zap,
  Users,
  Settings,
  Activity,
  ChevronLeft,
  ChevronRight,
  Moon,
  Sun,
  Menu,
  X,
  Server,
  GitBranch,
  Clock
} from 'lucide-react';

const NewSidebar = ({ activeView, setActiveView, models = [], theme, toggleTheme }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [gpuStats, setGpuStats] = useState({ gpus: [] });

  useEffect(() => {
    // Check if sidebar should be collapsed on load (for smaller screens)
    const checkScreenSize = () => {
      if (window.innerWidth < 1024) {
        setIsCollapsed(true);
      }
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);

    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Fetch GPU stats
  useEffect(() => {
    const fetchGpuStats = async () => {
      try {
        const response = await fetch('/orchestrator/gpu-stats');
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
  }, []);

  const menuItems = [
    {
      section: 'Overview',
      items: [
        {
          id: 'dashboard',
          label: 'Dashboard',
          icon: LayoutGrid,
          description: 'System overview'
        },
        {
          id: 'all-models',
          label: 'Model Library',
          icon: Layers,
          description: 'Browse all models'
        },
        {
          id: 'deployed',
          label: 'Active Models',
          icon: Server,
          description: 'Running models',
          badge: models.filter(m => m.status === 'running').length || null
        }
      ]
    },
    {
      section: 'Models',
      items: [
        {
          id: 'llm',
          label: 'Language Models',
          icon: Cpu,
          description: 'LLM models'
        },
        {
          id: 'embedding',
          label: 'Embeddings',
          icon: Database,
          description: 'Vector models'
        },
        {
          id: 'quantized',
          label: 'Quantized',
          icon: Zap,
          description: 'Optimized models',
          badge: 'Fast'
        }
      ]
    },
    {
      section: 'Tools',
      items: [
        {
          id: 'chat',
          label: 'Playground',
          icon: Users,
          description: 'Chat interface'
        },
        {
          id: 'monitoring',
          label: 'GPU Monitor',
          icon: Activity,
          description: 'Resource usage'
        },
        {
          id: 'api-keys',
          label: 'API Keys',
          icon: Settings,
          description: 'Manage keys'
        }
      ]
    }
  ];

  // Calculate total GPU usage
  const calculateGpuUsage = () => {
    if (gpuStats.gpus.length === 0) return { used: 0, total: 48, percentage: 0 };

    const totalMemory = gpuStats.gpus.reduce((sum, gpu) => sum + gpu.memory_total_mb, 0);
    const usedMemory = gpuStats.gpus.reduce((sum, gpu) => sum + gpu.memory_used_mb, 0);
    const percentage = totalMemory > 0 ? Math.round((usedMemory / totalMemory) * 100) : 0;

    return {
      used: Math.round(usedMemory / 1024),
      total: Math.round(totalMemory / 1024),
      percentage
    };
  };

  const gpuUsage = calculateGpuUsage();

  return (
    <>
      {/* Mobile Menu Button */}
      <button
        className="mobile-menu-btn"
        onClick={() => setIsMobileOpen(true)}
        aria-label="Open menu"
      >
        <Menu size={24} />
      </button>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`sidebar ${isCollapsed ? 'sidebar-collapsed' : ''} ${isMobileOpen ? 'sidebar-mobile-open' : ''}`}
      >
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-icon">
              <GitBranch size={24} />
            </div>
            {!isCollapsed && (
              <div className="logo-text">
                <h2>Model Hub</h2>
                <p className="text-muted">AI Infrastructure</p>
              </div>
            )}
          </div>

          {/* Collapse Toggle - Desktop Only */}
          <button
            className="sidebar-toggle desktop-only"
            onClick={() => setIsCollapsed(!isCollapsed)}
            aria-label="Toggle sidebar"
          >
            {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
          </button>

          {/* Close Button - Mobile Only */}
          <button
            className="sidebar-toggle mobile-only"
            onClick={() => setIsMobileOpen(false)}
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          {menuItems.map((group, groupIndex) => (
            <div key={groupIndex} className="nav-section">
              {!isCollapsed && (
                <div className="nav-section-title">{group.section}</div>
              )}
              <div className="nav-items">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeView === item.id;

                  return (
                    <button
                      key={item.id}
                      className={`nav-item ${isActive ? 'nav-item-active' : ''}`}
                      onClick={() => {
                        setActiveView(item.id);
                        setIsMobileOpen(false);
                      }}
                      title={isCollapsed ? item.label : ''}
                    >
                      <div className="nav-item-icon">
                        <Icon size={20} />
                      </div>
                      {!isCollapsed && (
                        <>
                          <div className="nav-item-content">
                            <span className="nav-item-label">{item.label}</span>
                            <span className="nav-item-description">{item.description}</span>
                          </div>
                          {item.badge && (
                            <div className={`nav-item-badge ${typeof item.badge === 'number' ? 'badge-count' : 'badge-text'}`}>
                              {item.badge}
                            </div>
                          )}
                        </>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="sidebar-footer">
          {/* GPU Usage */}
          {!isCollapsed && (
            <div className="gpu-usage-card">
              <div className="gpu-usage-header">
                <Activity size={16} />
                <span>GPU Usage</span>
                <span className="gpu-usage-value">{gpuUsage.percentage}%</span>
              </div>
              <div className="progress">
                <div
                  className="progress-bar"
                  style={{
                    width: `${gpuUsage.percentage}%`,
                    background: gpuUsage.percentage > 80
                      ? 'linear-gradient(90deg, #EF4444, #DC2626)'
                      : gpuUsage.percentage > 60
                      ? 'linear-gradient(90deg, #F59E0B, #D97706)'
                      : 'linear-gradient(90deg, var(--color-primary), var(--color-primary-light))'
                  }}
                />
              </div>
              <div className="gpu-usage-footer">
                <span>{gpuUsage.used} GB / {gpuUsage.total} GB</span>
                <span>{models.filter(m => m.status === 'running').length} active</span>
              </div>
            </div>
          )}

          {/* Theme Toggle */}
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? (
              <Sun size={20} />
            ) : (
              <Moon size={20} />
            )}
            {!isCollapsed && (
              <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
            )}
          </button>

          {/* Version Info */}
          {!isCollapsed && (
            <div className="sidebar-version">
              <Clock size={14} />
              <span>v2.0.0</span>
            </div>
          )}
        </div>
      </aside>
    </>
  );
};

export default NewSidebar;