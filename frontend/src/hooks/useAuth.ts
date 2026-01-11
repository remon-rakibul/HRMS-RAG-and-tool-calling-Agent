/** Auth hook with auto-login */

import { useState, useEffect } from 'react';
import { authApi } from '../api/auth';
import { tokenStorage } from '../utils/token';

const AUTO_LOGIN_EMAIL = 'hrms@recombd.com';
const AUTO_LOGIN_PASSWORD = '12345678';

export const useAuth = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const autoLogin = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Check if we already have tokens
        if (tokenStorage.hasTokens()) {
          setIsAuthenticated(true);
          setIsLoading(false);
          return;
        }

        // Auto-login with hardcoded credentials
        await authApi.login(AUTO_LOGIN_EMAIL, AUTO_LOGIN_PASSWORD);
        setIsAuthenticated(true);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Login failed';
        setError(errorMessage);
        setIsAuthenticated(false);
        console.error('Auto-login error:', err);
      } finally {
        setIsLoading(false);
      }
    };

    autoLogin();
  }, []);

  const logout = async () => {
    try {
      await authApi.logout();
      setIsAuthenticated(false);
    } catch (err) {
      console.error('Logout error:', err);
      // Clear tokens even if API call fails
      tokenStorage.clearTokens();
      setIsAuthenticated(false);
    }
  };

  return {
    isAuthenticated,
    isLoading,
    error,
    logout,
  };
};

