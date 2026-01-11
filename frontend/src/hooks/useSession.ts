/** Session management hook */

import { useState, useEffect } from 'react';
import { agentApi, type SessionContext } from '../api/agent';
import { getSessionId } from '../utils/urlParams';
import { useAuth } from './useAuth';

export const useSession = () => {
  const { isAuthenticated } = useAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionContext, setSessionContext] = useState<SessionContext | null>(null);
  const [employeeId, setEmployeeId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSession = async () => {
      if (!isAuthenticated) {
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        // Get sessionId from URL params
        const urlSessionId = getSessionId();
        if (!urlSessionId) {
          setError('No sessionId found in URL parameters');
          setIsLoading(false);
          return;
        }

        setSessionId(urlSessionId);

        // Fetch session context to get employee_id
        const context = await agentApi.getSession(urlSessionId);
        setSessionContext(context);
        setEmployeeId(context.employee_id);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load session';
        setError(errorMessage);
        console.error('Session load error:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadSession();
  }, [isAuthenticated]);

  return {
    sessionId,
    sessionContext,
    employeeId,
    isLoading,
    error,
  };
};

