/** Document Review Card component for HITL document review */

import React, { useState } from 'react';
import type { InterruptData } from '../hooks/useChat';

interface DocumentReviewCardProps {
  interruptData: InterruptData;
  onUseAll: () => void;
  onAddContext: (context: string) => void;
  onRejectAll: () => void;
  disabled?: boolean;
}

export const DocumentReviewCard: React.FC<DocumentReviewCardProps> = ({
  interruptData,
  onUseAll,
  onAddContext,
  onRejectAll,
  disabled = false,
}) => {
  const [additionalContext, setAdditionalContext] = useState('');
  const [showContextInput, setShowContextInput] = useState(false);

  const handleAddContext = () => {
    if (additionalContext.trim()) {
      onAddContext(additionalContext);
    } else {
      setShowContextInput(true);
    }
  };

  // If resolved, show a simple resolved state
  if (interruptData.resolved) {
    return (
      <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 border border-gray-300 dark:border-gray-600 opacity-60 max-w-lg mx-auto">
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-sm">Documents reviewed</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-purple-50 dark:bg-purple-900/20 rounded-xl p-5 border-2 border-purple-400 dark:border-purple-500 shadow-lg max-w-lg mx-auto">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 bg-purple-100 dark:bg-purple-800 rounded-full flex-shrink-0">
          <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-purple-800 dark:text-purple-200 text-lg">
            Document Review
          </h3>
          <p className="text-xs text-purple-600 dark:text-purple-400 uppercase tracking-wide">
            {interruptData.document_count || 0} document(s) retrieved
          </p>
        </div>
      </div>

      {/* Message */}
      <p className="text-gray-800 dark:text-gray-200 mb-4 text-sm leading-relaxed">
        {interruptData.message}
      </p>

      {/* Documents Preview */}
      {interruptData.documents && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4 border border-gray-200 dark:border-gray-700 max-h-64 overflow-y-auto">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-2">
            Retrieved Documents
          </span>
          <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono text-xs leading-relaxed">
            {interruptData.documents}
          </div>
        </div>
      )}

      {/* Additional Context Input */}
      {showContextInput && (
        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">
            Add Additional Context
          </label>
          <textarea
            value={additionalContext}
            onChange={(e) => setAdditionalContext(e.target.value)}
            placeholder="Enter additional context or information..."
            rows={3}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-none"
            disabled={disabled}
          />
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        {interruptData.options?.includes('use_all') && (
          <button
            onClick={onUseAll}
            disabled={disabled}
            className="flex-1 min-w-[120px] px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Use All
          </button>
        )}
        {interruptData.options?.includes('add_context') && (
          <button
            onClick={handleAddContext}
            disabled={disabled}
            className="flex-1 min-w-[120px] px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {showContextInput && additionalContext.trim() ? 'Submit Context' : 'Add Context'}
          </button>
        )}
        {interruptData.options?.includes('reject_all') && (
          <button
            onClick={onRejectAll}
            disabled={disabled}
            className="flex-1 min-w-[120px] px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Reject All
          </button>
        )}
      </div>
    </div>
  );
};
