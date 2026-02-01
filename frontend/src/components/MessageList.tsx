/** Message list component with HITL interrupt support */

import { useEffect, useRef } from 'react';
import type { Message } from '../hooks/useChat';
import { ApprovalCard } from './ApprovalCard';
import { MarkdownContent } from './MarkdownContent';

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  isAwaitingApproval?: boolean;
  onApprove?: (data: Record<string, any>) => void;
  onReject?: () => void;
  isDark?: boolean;
}

export const MessageList = ({ 
  messages, 
  isStreaming,
  isAwaitingApproval: _isAwaitingApproval = false,
  onApprove,
  onReject,
}: MessageListProps) => {
  // isAwaitingApproval is available via _isAwaitingApproval if needed for future use
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">
      {messages.length === 0 ? (
        <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
          <div className="inline-block p-4 rounded-full bg-gray-100 dark:bg-gray-800 mb-4">
            <svg className="w-12 h-12 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <p className="text-lg font-medium">No messages yet</p>
          <p className="text-sm">Start a conversation!</p>
        </div>
      ) : (
        <>
          {messages.map((message, index) => {
            // Handle interrupt messages specially - render ApprovalCard
            if (message.role === 'interrupt' && message.interruptData) {
              return (
                <div key={message.id} className="flex justify-center my-4">
                  <ApprovalCard
                    interruptData={message.interruptData}
                    onApprove={(data) => onApprove?.(data)}
                    onReject={() => onReject?.()}
                    disabled={isStreaming || message.interruptData.resolved}
                  />
                </div>
              );
            }

            // Regular user/assistant messages
            const isUser = message.role === 'user';
            const showAvatar = index === 0 || messages[index - 1].role !== message.role;
            
            return (
              <div
                key={message.id}
                className={`flex items-end gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
              >
                {/* Avatar */}
                {showAvatar && (
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                    isUser 
                      ? 'bg-gradient-to-br from-blue-500 to-blue-600' 
                      : 'bg-gradient-to-br from-gray-400 to-gray-500 dark:from-gray-600 dark:to-gray-700'
                  }`}>
                    {isUser ? (
                      <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
                        <path d="M15 7v2a4 4 0 01-4 4H9.828l-1.766 1.767c.28.149.599.233.938.233h2l3 3v-3h2a2 2 0 002-2V9a2 2 0 00-2-2h-1z" />
                      </svg>
                    )}
                  </div>
                )}
                {!showAvatar && <div className="w-8" />}
                
                {/* Message Bubble */}
                <div
                  className={`max-w-[75%] md:max-w-[65%] rounded-2xl px-4 py-2.5 shadow-sm transition-all ${
                    isUser
                      ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-br-sm'
                      : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100 border border-gray-200 dark:border-gray-700 rounded-bl-sm'
                  }`}
                >
                  {isUser ? (
                    // User messages: plain text
                    <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                      {message.content}
                    </div>
                  ) : (
                    // Assistant messages: markdown rendered
                    <MarkdownContent content={message.content} />
                  )}
                  {!isUser && isStreaming && message.id === messages[messages.length - 1]?.id && (
                    <span className="inline-block w-2 h-4 bg-gray-400 dark:bg-gray-500 animate-pulse ml-1.5 mt-1"></span>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
};
