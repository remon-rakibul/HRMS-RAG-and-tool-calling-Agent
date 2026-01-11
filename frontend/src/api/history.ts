/** Chat history API endpoints */

import { apiClient } from './client';

export interface ChatMessageHistory {
  role: string;
  content: string;
  created_at: string;
}

export interface ThreadMessagesResponse {
  thread_id: string;
  messages: ChatMessageHistory[];
  total: number;
}

export const historyApi = {
  getThreadMessages: async (threadId: string): Promise<ThreadMessagesResponse> => {
    const response = await apiClient.get<ThreadMessagesResponse>(`/history/${threadId}`);
    return response.data;
  },
};

