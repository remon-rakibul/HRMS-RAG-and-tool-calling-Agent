/** Agent API endpoints for session and chat */

import { apiClient } from './client';
import { tokenStorage } from '../utils/token';

export interface SessionContext {
  session_id: string;
  employee_id: number;
  employee_name: string;
}

export interface ChatRequest {
  message: string;
  thread_id?: string;
  session_id?: string;
}

export interface InterruptPayload {
  action: string;  // 'leave_application', 'verify_employee', 'confirm_leave_approval', 'tool_approval', etc.
  message: string;
  step?: number;
  total_steps?: number;
  details?: Record<string, any>;
  pending_actions?: Array<{tool: string; args: Record<string, any>}>;
  documents?: string;
  document_count?: number;
  current_values?: Record<string, any>;
  editable_fields?: string[];
  validation_errors?: string[];
  question?: string;
  options?: string[];  // ['approve', 'reject', 'edit', 'confirm', 'cancel', 'use_all', 'add_context', 'reject_all']
}

export interface ChatMessage {
  type: 'token' | 'done' | 'error' | 'interrupt';
  content?: string;
  thread_id?: string;
  interrupt_data?: InterruptPayload;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://0.0.0.0:8000/api/v1';

/**
 * Helper to refresh token and return a valid access token.
 * If refresh fails, returns null and clears tokens.
 */
const getValidAccessToken = async (): Promise<string | null> => {
  const accessToken = tokenStorage.getAccessToken();
  if (!accessToken) {
    return null;
  }
  return accessToken;
};

/**
 * Makes a streaming fetch request with automatic 401 retry after token refresh.
 */
const fetchWithTokenRefresh = async (
  url: string,
  options: RequestInit,
  onError: (error: string) => void
): Promise<Response | null> => {
  let accessToken = await getValidAccessToken();
  if (!accessToken) {
    onError('No access token available. Please refresh the page.');
    return null;
  }

  // First attempt
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`,
    },
  });

  // If 401, try to refresh token and retry once
  if (response.status === 401) {
    const refreshToken = tokenStorage.getRefreshToken();
    if (!refreshToken) {
      tokenStorage.clearTokens();
      onError('Session expired. Please refresh the page to re-login.');
      return null;
    }

    try {
      // Attempt token refresh
      const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!refreshResponse.ok) {
        tokenStorage.clearTokens();
        onError('Session expired. Please refresh the page to re-login.');
        return null;
      }

      const { access_token, refresh_token } = await refreshResponse.json();
      tokenStorage.setTokens(access_token, refresh_token);
      accessToken = access_token;

      // Retry the original request with new token
      response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${accessToken}`,
        },
      });
    } catch (refreshError) {
      tokenStorage.clearTokens();
      onError('Failed to refresh session. Please refresh the page.');
      return null;
    }
  }

  return response;
};

export const agentApi = {
  getSession: async (sessionId: string): Promise<SessionContext> => {
    const response = await apiClient.get<SessionContext>(`/agent/session/${sessionId}`);
    return response.data;
  },

  sendChatMessage: async (
    message: string,
    threadId: string | null,
    sessionId: string | null,
    onToken: (token: string) => void,
    onComplete: (fullResponse: string) => void,
    onError: (error: string) => void,
    onInterrupt?: (payload: InterruptPayload) => void
  ): Promise<void> => {
    const url = `${API_BASE_URL}/chat`;

    const response = await fetchWithTokenRefresh(
      url,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          thread_id: threadId || undefined,
          session_id: sessionId || undefined,
        }),
      },
      onError
    );

    if (!response) {
      return; // Error already handled by fetchWithTokenRefresh
    }

    if (!response.ok) {
      onError(`HTTP ${response.status}: ${response.statusText}`);
      return;
    }

    // Handle SSE streaming
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';

    if (!reader) {
      onError('No response body');
      return;
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: ChatMessage = JSON.parse(line.slice(6));
              
              if (data.type === 'token' && data.content) {
                fullResponse += data.content;
                onToken(data.content);
              } else if (data.type === 'done') {
                onComplete(data.content || fullResponse);
              } else if (data.type === 'interrupt' && data.interrupt_data && onInterrupt) {
                onInterrupt(data.interrupt_data);
                return;  // Stop reading, wait for resume
              } else if (data.type === 'error' && data.content) {
                onError(data.content);
                return;
              }
            } catch (e) {
              console.error('Parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Unknown error');
    }
  },

  resumeChat: async (
    threadId: string,
    sessionId: string | null,
    resumeData: Record<string, any>,
    onToken: (token: string) => void,
    onComplete: (fullResponse: string) => void,
    onError: (error: string) => void,
    onInterrupt?: (payload: InterruptPayload) => void
  ): Promise<void> => {
    const url = `${API_BASE_URL}/chat/resume`;

    const response = await fetchWithTokenRefresh(
      url,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: threadId,
          session_id: sessionId || undefined,
          resume_data: resumeData,
        }),
      },
      onError
    );

    if (!response) {
      return; // Error already handled by fetchWithTokenRefresh
    }

    if (!response.ok) {
      onError(`HTTP ${response.status}: ${response.statusText}`);
      return;
    }

    // Handle SSE streaming (same as sendChatMessage)
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';

    if (!reader) {
      onError('No response body');
      return;
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: ChatMessage = JSON.parse(line.slice(6));
              
              if (data.type === 'token' && data.content) {
                fullResponse += data.content;
                onToken(data.content);
              } else if (data.type === 'done') {
                onComplete(data.content || fullResponse);
              } else if (data.type === 'interrupt' && data.interrupt_data && onInterrupt) {
                onInterrupt(data.interrupt_data);
                return;  // Stop reading, wait for next resume
              } else if (data.type === 'error' && data.content) {
                onError(data.content);
                return;
              }
            } catch (e) {
              console.error('Parse error:', e);
            }
          }
        }
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Unknown error');
    }
  },

  deleteThreadMemory: async (threadId: string): Promise<void> => {
    try {
      await apiClient.delete(`/memory/${threadId}`);
    } catch (error: any) {
      // If thread doesn't exist (404), that's fine - no checkpoints to delete
      // If it's a different error, we'll let it propagate
      if (error.response?.status === 404) {
        console.log(`No memory found for thread ${threadId}, continuing...`);
        return;
      }
      throw error;
    }
  },
};

