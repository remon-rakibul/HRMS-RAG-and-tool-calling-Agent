/** Agent API endpoints for session and chat */

import { apiClient } from './client';

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

export interface ChatMessage {
  type: 'token' | 'done' | 'error';
  content?: string;
  thread_id?: string;
}

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
    onError: (error: string) => void
  ): Promise<void> => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      onError('No access token available');
      return;
    }

    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://0.0.0.0:8000/api/v1';
    const url = `${API_BASE_URL}/chat`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        thread_id: threadId || undefined,
        session_id: sessionId || undefined,
      }),
    });

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

