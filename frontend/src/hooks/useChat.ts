/** Chat streaming hook with HITL interrupt support */

import { useState, useCallback } from 'react';
import { agentApi } from '../api/agent';
import type { InterruptPayload } from '../api/agent';

export interface InterruptData {
  action: string;
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
  options?: string[];
  threadId: string;
  resolved?: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'interrupt';
  content: string;
  timestamp: Date;
  interruptData?: InterruptData;
}

export const useChat = (threadId: string | null, sessionId: string | null) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isAwaitingApproval, setIsAwaitingApproval] = useState(false);
  const [pendingInterrupt, setPendingInterrupt] = useState<Message | null>(null);
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
            setMessages((prev) => {
              const exists = prev.some((msg) => msg.id === assistantMessageId);
              if (!exists) {
                // Message was removed, re-add it
                return [...prev, { ...assistantMessage, content: fullResponse }];
              }
              return prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: fullResponse }
                  : msg
              );
            });
          },
          // onComplete
          (completeResponse: string) => {
            const finalContent = completeResponse || fullResponse;
            setMessages((prev) => {
              const exists = prev.some((msg) => msg.id === assistantMessageId);
              if (!exists && finalContent.trim()) {
                // Message was removed but we have content, re-add it
                return [...prev, { ...assistantMessage, content: finalContent }];
              }
              return prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: finalContent }
                  : msg
              );
            });
            setIsStreaming(false);
          },
          // onError
          (errorMessage: string) => {
            setError(errorMessage);
            setIsStreaming(false);
            // Remove the empty assistant placeholder on error, keep user message
            setMessages((prev) =>
              prev.filter((msg) => msg.id !== assistantMessageId || msg.content.trim() !== '')
            );
          },
          // onInterrupt
          (interruptPayload: InterruptPayload) => {
            setIsStreaming(false);
            setIsAwaitingApproval(true);
            
            // Remove the empty assistant placeholder
            setMessages((prev) => 
              prev.filter((msg) => msg.id !== assistantMessageId || msg.content.trim() !== '')
            );
            
            // Add interrupt message
            const interruptMessage: Message = {
              id: (Date.now() + 2).toString(),
              role: 'interrupt',
              content: interruptPayload.message,
              timestamp: new Date(),
              interruptData: {
                action: interruptPayload.action,
                message: interruptPayload.message,
                step: interruptPayload.step,
                total_steps: interruptPayload.total_steps,
                details: interruptPayload.details,
                pending_actions: interruptPayload.pending_actions,
                documents: interruptPayload.documents,
                document_count: interruptPayload.document_count,
                current_values: interruptPayload.current_values,
                editable_fields: interruptPayload.editable_fields,
                validation_errors: interruptPayload.validation_errors,
                question: interruptPayload.question,
                options: interruptPayload.options || ['approve', 'reject'],
                threadId: threadId,
                resolved: false,
              },
            };
            
            setMessages((prev) => [...prev, interruptMessage]);
            setPendingInterrupt(interruptMessage);
          }
        );
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        setError(errorMessage);
        setIsStreaming(false);
        // Remove the empty placeholder on error
        setMessages((prev) =>
          prev.filter((msg) => msg.id !== assistantMessageId || msg.content.trim() !== '')
        );
      }
    },
    [threadId, sessionId]
  );

  // Resume after approval/rejection
  const resumeWithResponse = useCallback(
    async (response: Record<string, any>) => {
      if (!threadId || !sessionId || !pendingInterrupt) {
        return;
      }

      // Mark interrupt as resolved
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === pendingInterrupt.id && msg.interruptData
            ? { ...msg, interruptData: { ...msg.interruptData, resolved: true } }
            : msg
        )
      );

      setIsAwaitingApproval(false);
      setPendingInterrupt(null);
      setIsStreaming(true);

      // Create new assistant placeholder for the continued response
      const assistantMessageId = Date.now().toString();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      let fullResponse = '';

      try {
        await agentApi.resumeChat(
          threadId,
          sessionId,
          response,
          // onToken
          (token: string) => {
            fullResponse += token;
            setMessages((prev) => {
              const exists = prev.some((msg) => msg.id === assistantMessageId);
              if (!exists) {
                return [...prev, { ...assistantMessage, content: fullResponse }];
              }
              return prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: fullResponse }
                  : msg
              );
            });
          },
          // onComplete
          (completeResponse: string) => {
            const finalContent = completeResponse || fullResponse;
            setMessages((prev) => {
              const exists = prev.some((msg) => msg.id === assistantMessageId);
              if (!exists && finalContent.trim()) {
                return [...prev, { ...assistantMessage, content: finalContent }];
              }
              return prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: finalContent }
                  : msg
              );
            });
            setIsStreaming(false);
          },
          // onError
          (errorMessage: string) => {
            setError(errorMessage);
            setIsStreaming(false);
            // Remove the empty placeholder on error
            setMessages((prev) =>
              prev.filter((msg) => msg.id !== assistantMessageId || msg.content.trim() !== '')
            );
          },
          // onInterrupt (nested interrupts for multi-step flows)
          (interruptPayload: InterruptPayload) => {
            setIsStreaming(false);
            setIsAwaitingApproval(true);
            
            // Remove empty assistant placeholder
            setMessages((prev) => 
              prev.filter((msg) => msg.id !== assistantMessageId || msg.content.trim() !== '')
            );
            
            // Add new interrupt message
            const interruptMessage: Message = {
              id: (Date.now() + 2).toString(),
              role: 'interrupt',
              content: interruptPayload.message,
              timestamp: new Date(),
              interruptData: {
                action: interruptPayload.action,
                message: interruptPayload.message,
                step: interruptPayload.step,
                total_steps: interruptPayload.total_steps,
                details: interruptPayload.details,
                pending_actions: interruptPayload.pending_actions,
                documents: interruptPayload.documents,
                document_count: interruptPayload.document_count,
                current_values: interruptPayload.current_values,
                editable_fields: interruptPayload.editable_fields,
                validation_errors: interruptPayload.validation_errors,
                question: interruptPayload.question,
                options: interruptPayload.options || ['approve', 'reject'],
                threadId: threadId,
                resolved: false,
              },
            };
            
            setMessages((prev) => [...prev, interruptMessage]);
            setPendingInterrupt(interruptMessage);
          }
        );
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        setError(errorMessage);
        setIsStreaming(false);
        // Remove the empty placeholder on error
        setMessages((prev) =>
          prev.filter((msg) => msg.id !== assistantMessageId || msg.content.trim() !== '')
        );
      }
    },
    [threadId, sessionId, pendingInterrupt]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    setPendingInterrupt(null);
    setIsAwaitingApproval(false);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isStreaming,
    isAwaitingApproval,
    pendingInterrupt,
    error,
    sendMessage,
    resumeWithResponse,
    clearMessages,
    clearError,
  };
};
