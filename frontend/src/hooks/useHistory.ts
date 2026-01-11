/** Chat history hook */

import { useState, useEffect } from 'react';
import { historyApi, type ChatMessageHistory } from '../api/history';
import type { Message } from './useChat';

export const useHistory = (threadId: string | null) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = async () => {
    if (!threadId) {
      setIsLoading(false);
      setMessages([]);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const response = await historyApi.getThreadMessages(threadId);
      
      // Convert API messages to Message format
      const convertedMessages: Message[] = response.messages.map((msg: ChatMessageHistory, index: number) => ({
        id: `${threadId}-${index}`,
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        timestamp: new Date(msg.created_at),
      }));

      setMessages(convertedMessages);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load history';
      setError(errorMessage);
      console.error('History load error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [threadId]);

  const clearMessages = () => {
    setMessages([]);
    setError(null);
  };

  return {
    messages,
    isLoading,
    error,
    refetch: loadHistory,
    clearMessages,
  };
};

