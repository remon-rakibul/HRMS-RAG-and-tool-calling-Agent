/** Chat streaming hook */

import { useState, useCallback } from 'react';
import { agentApi } from '../api/agent';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export const useChat = (threadId: string | null, sessionId: string | null) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Don't clear messages when threadId changes - let history hook handle initial load
  // Messages will be merged with history in ChatInterface

  const sendMessage = useCallback(
    async (message: string) => {
      if (!threadId || !sessionId) {
        setError('Thread ID or Session ID not available');
        return;
      }

      // Add user message
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: message,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // Create assistant message placeholder
      const assistantMessageId = (Date.now() + 1).toString();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      setIsStreaming(true);
      setError(null);

      let fullResponse = '';

      try {
        await agentApi.sendChatMessage(
          message,
          threadId,
          sessionId,
          // onToken
          (token: string) => {
            fullResponse += token;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: fullResponse }
                  : msg
              )
            );
          },
          // onComplete
          (completeResponse: string) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: completeResponse || fullResponse }
                  : msg
              )
            );
            setIsStreaming(false);
          },
          // onError
          (errorMessage: string) => {
            setError(errorMessage);
            setIsStreaming(false);
            // Update assistant message with error
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: `Error: ${errorMessage}` }
                  : msg
              )
            );
          }
        );
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        setError(errorMessage);
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: `Error: ${errorMessage}` }
              : msg
          )
        );
      }
    },
    [threadId, sessionId]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    clearMessages,
  };
};

