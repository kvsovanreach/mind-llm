import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    const tokenExpires = localStorage.getItem('token_expires');

    if (storedToken && tokenExpires) {
      // Check if token is still valid
      if (Date.now() < parseInt(tokenExpires)) {
        setToken(storedToken);
        setIsAuthenticated(true);

        // Set up token refresh before expiry
        const timeUntilExpiry = parseInt(tokenExpires) - Date.now();
        if (timeUntilExpiry > 0) {
          setTimeout(() => {
            logout();
          }, timeUntilExpiry);
        }
      } else {
        // Token expired, clear it
        logout();
      }
    }
    setLoading(false);
  }, []);

  const login = (authToken) => {
    setToken(authToken);
    setIsAuthenticated(true);

    // Set up auto-logout on token expiry
    const tokenExpires = localStorage.getItem('token_expires');
    if (tokenExpires) {
      const timeUntilExpiry = parseInt(tokenExpires) - Date.now();
      if (timeUntilExpiry > 0) {
        setTimeout(() => {
          logout();
        }, timeUntilExpiry);
      }
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('token_expires');
    setToken(null);
    setIsAuthenticated(false);
  };

  const getAuthHeaders = () => {
    if (token) {
      return {
        'Authorization': `Bearer ${token}`,
      };
    }
    return {};
  };

  // Function to make authenticated API calls
  const fetchWithAuth = async (url, options = {}) => {
    const authHeaders = getAuthHeaders();

    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        ...authHeaders,
      },
    });

    // Handle 401 responses (unauthorized)
    if (response.status === 401) {
      logout();
      throw new Error('Authentication expired');
    }

    return response;
  };

  const value = {
    isAuthenticated,
    token,
    loading,
    login,
    logout,
    getAuthHeaders,
    fetchWithAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;