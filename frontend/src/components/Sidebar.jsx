import React, { useState, useEffect, useRef } from 'react';
import {
  LayoutDashboard,
  MessageCircle,
  Key,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  FolderOpen,
  LogOut
} from 'lucide-react';

const Sidebar = ({ activeView, setActiveView, models = [], onCollapseChange, onLogout }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const sidebarRef = useRef(null);

  // Auto-adjust for screen size
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024 && window.innerWidth < 1280) {
        setIsCollapsed(true);
      } else if (window.innerWidth >= 1280) {
        setIsCollapsed(false);
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const navigation = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      badge: null
    },
    {
      id: 'all-models',
      label: 'Model Library',
      icon: FolderOpen,
      badge: models.length
    },
    {
      id: 'chat',
      label: 'Chat Playground',
      icon: MessageCircle
    },
    {
      id: 'api-keys',
      label: 'API Keys',
      icon: Key
    }
  ];



  return (
    <>
      {/* Mobile Menu Toggle */}
      <button
        className="lg:hidden fixed top-4 left-4 z-50 btn btn-icon bg-white dark:bg-gray-800 shadow-lg"
        onClick={() => setIsMobileOpen(true)}
      >
        <Menu size={20} />
      </button>

      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        ref={sidebarRef}
        className={`
          app-sidebar
          ${isCollapsed ? 'collapsed' : ''}
          ${isMobileOpen ? 'mobile-open' : 'mobile-hidden lg:transform-none'}
        `}
        style={{ position: 'relative' }}
      >
        <div className="h-full flex flex-col">
          {/* Sidebar Header */}
          <div className="p-4 border-b border-gray-700">
            <div className="flex items-center justify-between">
              <div className={`flex items-center gap-3 ${isCollapsed ? 'justify-center' : ''}`}>
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-lg">
                  M
                </div>
                {!isCollapsed && (
                  <div>
                    <h1 className="text-lg font-bold text-white">Model Hub</h1>
                    <p className="text-xs text-gray-400">AI Infrastructure</p>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* Mobile close button */}
                <button
                  className="lg:hidden btn btn-icon btn-ghost"
                  onClick={() => setIsMobileOpen(false)}
                >
                  <X size={18} />
                </button>
              </div>
            </div>

          </div>


          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-3">
            <ul className="space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                const isActive = activeView === item.id;

                return (
                  <li key={item.id}>
                    <button
                      onClick={() => {
                        setActiveView(item.id);
                        setIsMobileOpen(false);
                      }}
                      className={`
                        w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                        transition-all duration-200 relative group
                        ${isActive
                          ? 'bg-blue-900/30 text-blue-400'
                          : 'hover:bg-gray-800 text-gray-400 hover:text-gray-200'
                        }
                        ${isCollapsed ? 'justify-center' : ''}
                      `}
                    >
                      {/* Active Indicator */}
                      {isActive && (
                        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full" />
                      )}

                      <Icon size={20} className={isActive ? 'text-blue-400' : 'text-gray-400'} />

                      {!isCollapsed && (
                        <>
                          <span className="flex-1 text-left text-sm font-medium">
                            {item.label}
                          </span>
                          {item.badge !== null && item.badge !== undefined && (
                            <span className={`
                              badge
                              ${item.badgeType === 'success' ? 'badge-success' :
                                item.badgeType === 'warning' ? 'badge-warning' :
                                'badge-primary'}
                            `}>
                              {item.badge}
                            </span>
                          )}
                        </>
                      )}

                      {/* Tooltip for collapsed state */}
                      {isCollapsed && (
                        <div className="absolute left-full ml-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity shadow-xl z-50">
                          {item.label}
                        </div>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Logout Button at Bottom */}
          <div className="mt-auto p-3 border-t border-gray-700">
            <button
              onClick={onLogout}
              className="nav-link nav-link-danger w-full"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: isCollapsed ? '0' : '0.75rem',
                justifyContent: isCollapsed ? 'center' : 'flex-start',
                padding: '0.75rem',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444',
                borderRadius: '0.5rem',
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.2s',
                fontSize: '0.875rem',
                fontWeight: '500'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
              }}
            >
              <LogOut size={20} />
              {!isCollapsed && <span>Logout</span>}
            </button>
          </div>

        </div>

        {/* Collapse toggle - positioned at middle edge of sidebar */}
        <button
          className="hidden lg:flex"
          onClick={() => {
            setIsCollapsed(!isCollapsed);
            onCollapseChange && onCollapseChange(!isCollapsed);
          }}
          style={{
            position: 'absolute',
            right: isCollapsed ? '-24px' : '-12px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '24px',
            height: '48px',
            backgroundColor: '#1f2937',
            border: '1px solid #374151',
            borderRadius: '0 0.375rem 0.375rem 0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            zIndex: 2000,
            transition: 'all 0.2s',
            color: '#9ca3af'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#374151';
            e.currentTarget.style.color = '#ffffff';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#1f2937';
            e.currentTarget.style.color = '#9ca3af';
          }}
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </aside>
    </>
  );
};

export default Sidebar;