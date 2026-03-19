import { useState, useCallback } from 'react';
import { apiService } from '../services/api';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!apiService.getToken());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (userId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await apiService.requestToken(userId);
      setIsAuthenticated(true);
      return true;
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { error?: { message?: string } } } };
      setError(axiosError.response?.data?.error?.message || 'Login failed');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    apiService.setToken(null);
    setIsAuthenticated(false);
  }, []);

  return { isAuthenticated, isLoading, error, login, logout };
}
