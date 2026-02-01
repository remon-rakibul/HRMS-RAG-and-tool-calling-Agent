/** Main chat interface component */

import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useSession } from '../hooks/useSession';
import { useChat } from '../hooks/useChat';
import { useHistory } from '../hooks/useHistory';
import { useDarkMode } from '../hooks/useDarkMode';
import { agentApi } from '../api/agent';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { LoadingSpinner } from './LoadingSpinner';
import { DarkModeToggle } from './DarkModeToggle';

export const ChatInterface = () => {
  const { isDark, toggle: toggleDarkMode } = useDarkMode();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { employeeId, sessionId, isLoading: sessionLoading, error: sessionError } = useSession();
  const { 
    messages, 
    isStreaming, 
    isAwaitingApproval,
    error: chatError, 
    sendMessage, 
    resumeWithResponse,
    clearMessages,
    clearError,
  } = useChat(
    employeeId?.toString() || null,
    sessionId || null
  );
  const { messages: historyMessages, isLoading: historyLoading, clearMessages: clearHistoryMessages } = useHistory(
    employeeId?.toString() || null
  );
  const [isDeleting, setIsDeleting] = useState(false);

  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:25',message:'Component render with dark mode',data:{isDark,htmlHasDark:document.documentElement.classList.contains('dark'),htmlClassList:Array.from(document.documentElement.classList)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
  }, [isDark]);
  // #endregion

  // Merge history and current messages properly
  // Filter out new messages that are already in history (by content match)
  const newMessagesNotInHistory = messages.filter((newMsg) => {
    // Check if a message with same content and role exists in history
    return !historyMessages.some(
      (histMsg) => 
        histMsg.content === newMsg.content && 
        histMsg.role === newMsg.role
    );
  });
  
  // Combine: history first, then new messages
  const displayMessages = [...historyMessages, ...newMessagesNotInHistory].sort(
    (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
  );

  // Handle new chat button click
  const handleNewChat = async () => {
    if (!employeeId || isDeleting) return;

    try {
      setIsDeleting(true);
      const threadId = employeeId.toString();
      
      // Delete memory (checkpoints) for the thread if any exist
      // This will silently succeed even if no checkpoints exist (404 is handled)
      await agentApi.deleteThreadMemory(threadId);
      
      // Clear current messages from UI
      clearMessages();
      
      // Clear history messages from UI (set empty array)
      // We don't need to refetch since we want a fresh start
      // The history will be empty until new messages are sent
      clearHistoryMessages();
    } catch (err) {
      console.error('Error starting new chat:', err);
      // Only show error if it's not a 404 (thread not found is fine)
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      if (!errorMessage.includes('404') && !errorMessage.includes('not found')) {
        alert('Failed to start new chat. Please try again.');
      }
    } finally {
      setIsDeleting(false);
    }
  };

  // Handle HITL approval
  const handleApprove = async (data: Record<string, any>) => {
    await resumeWithResponse(data);
  };

  // Handle HITL rejection
  const handleReject = async () => {
    await resumeWithResponse({ action: 'reject', approved: false });
  };

  if (authLoading || sessionLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
        <LoadingSpinner />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-red-600 dark:text-red-400 mb-2">Authentication Failed</h2>
          <p className="text-gray-600 dark:text-gray-400">Please refresh the page to try again.</p>
        </div>
      </div>
    );
  }

  if (sessionError) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-red-600 dark:text-red-400 mb-2">Session Error</h2>
          <p className="text-gray-600 dark:text-gray-400">{sessionError}</p>
          <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
            Make sure you have a valid sessionId in the URL: ?sessionId=xxx
          </p>
        </div>
      </div>
    );
  }

  if (!employeeId || !sessionId) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-yellow-600 dark:text-yellow-400 mb-2">Waiting for Session</h2>
          <p className="text-gray-600 dark:text-gray-400">Loading employee information...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-2 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-800 dark:text-gray-100">HRMS Agent</h1>
            {employeeId && (
              <p className="text-xs text-gray-600 dark:text-gray-400">Employee ID: {employeeId}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleNewChat}
              disabled={isDeleting || isStreaming || isAwaitingApproval}
              className="p-2 text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
              title="Start a new chat"
            >
              {isDeleting ? (
                <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              )}
            </button>
            <DarkModeToggle isDark={isDark} onToggle={toggleDarkMode} />
          </div>
        </div>
      </div>

      {/* Error Display */}
      {chatError && (
        <div className="bg-red-100 dark:bg-red-900/30 border-l-4 border-red-500 dark:border-red-400 text-red-700 dark:text-red-300 p-2 flex items-center justify-between">
          <div>
            <p className="font-bold text-sm">Error</p>
            <p className="text-sm">{chatError}</p>
          </div>
          <div className="flex items-center gap-2">
            {(chatError.includes('expired') || chatError.includes('401') || chatError.includes('refresh')) && (
              <button
                onClick={() => window.location.reload()}
                className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
              >
                Refresh Page
              </button>
            )}
            <button
              onClick={() => clearError()}
              className="px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:underline"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      {historyLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : (
        <MessageList 
          messages={displayMessages} 
          isStreaming={isStreaming}
          isAwaitingApproval={isAwaitingApproval}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}

      {/* Approval pending banner */}
      {isAwaitingApproval && (
        <div className="bg-amber-100 dark:bg-amber-900/30 border-t border-amber-300 dark:border-amber-700 px-4 py-2 text-center">
          <span className="text-amber-800 dark:text-amber-200 text-sm font-medium">
            Waiting for your approval before proceeding...
          </span>
        </div>
      )}

      {/* Input */}
      <MessageInput onSend={sendMessage} disabled={isStreaming || isAwaitingApproval} />
    </div>
  );
};

