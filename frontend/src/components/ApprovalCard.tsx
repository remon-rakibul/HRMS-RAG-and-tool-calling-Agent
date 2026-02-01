/** Approval Card component for HITL interrupts */

import React, { useState } from 'react';
import type { InterruptData } from '../hooks/useChat';

interface ApprovalCardProps {
  interruptData: InterruptData;
  onApprove: (data: Record<string, any>) => void;
  onReject: () => void;
  disabled?: boolean;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  interruptData,
  onApprove,
  onReject,
  disabled = false,
}) => {
  const [remarks, setRemarks] = useState(interruptData.current_values?.remarks || '');
  const [editedValues, setEditedValues] = useState<Record<string, any>>(
    interruptData.current_values || {}
  );
  const [isEditing, setIsEditing] = useState(false);

  const handleApprove = () => {
    const responseData: Record<string, any> = {
      action: interruptData.options?.includes('confirm') ? 'confirm' : 'approve',
    };
    
    // Include remarks if editable
    if (interruptData.editable_fields?.includes('remarks') && remarks) {
      responseData.remarks = remarks;
    }
    
    // Include any edited values
    if (isEditing && Object.keys(editedValues).length > 0) {
      Object.assign(responseData, editedValues);
    }
    
    onApprove(responseData);
  };

  const handleReject = () => {
    onReject();
  };

  const handleEditValue = (key: string, value: string) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
  };

  // Determine button labels based on options
  const approveLabel = interruptData.options?.includes('confirm') ? 'Confirm' : 'Approve';
  const rejectLabel = interruptData.options?.includes('cancel') ? 'Cancel' : 'Reject';

  // If resolved, show a simple resolved state
  if (interruptData.resolved) {
    return (
      <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 border border-gray-300 dark:border-gray-600 opacity-60 max-w-md mx-auto">
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-sm">Response submitted</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-5 border-2 border-amber-400 dark:border-amber-500 shadow-lg max-w-md mx-auto">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 bg-amber-100 dark:bg-amber-800 rounded-full flex-shrink-0">
          <svg className="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-amber-800 dark:text-amber-200 text-lg">
            Action Required
          </h3>
          <p className="text-xs text-amber-600 dark:text-amber-400 uppercase tracking-wide">
            {interruptData.action.replace(/_/g, ' ')}
            {interruptData.step && interruptData.total_steps && (
              <span className="ml-2">
                (Step {interruptData.step} of {interruptData.total_steps})
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Message */}
      <p className="text-gray-800 dark:text-gray-200 mb-4 text-sm leading-relaxed">
        {interruptData.question || interruptData.message}
      </p>

      {/* Details */}
      {interruptData.details && Object.keys(interruptData.details).length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4 border border-gray-200 dark:border-gray-700">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
              Details
            </span>
            {interruptData.options?.includes('edit') && (
              <button
                onClick={() => setIsEditing(!isEditing)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
                disabled={disabled}
              >
                {isEditing ? 'Done' : 'Edit'}
              </button>
            )}
          </div>
          <dl className="space-y-2">
            {Object.entries(interruptData.details).map(([key, value]) => (
              <div key={key} className="flex justify-between items-center text-sm">
                <dt className="text-gray-500 dark:text-gray-400 capitalize">
                  {key.replace(/_/g, ' ')}:
                </dt>
                {isEditing && interruptData.editable_fields?.includes(key) ? (
                  <input
                    type="text"
                    value={editedValues[key] ?? String(value)}
                    onChange={(e) => handleEditValue(key, e.target.value)}
                    className="text-right bg-gray-100 dark:bg-gray-700 rounded px-2 py-1 text-gray-800 dark:text-gray-200 w-40 text-sm border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                    disabled={disabled}
                  />
                ) : (
                  <dd className="text-gray-800 dark:text-gray-200 font-medium text-right">
                    {String(value)}
                  </dd>
                )}
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Pending Actions (for tool_approval type) */}
      {interruptData.pending_actions && interruptData.pending_actions.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4 border border-gray-200 dark:border-gray-700">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-2">
            Pending Actions
          </span>
          <ul className="space-y-2">
            {interruptData.pending_actions.map((action, index) => (
              <li key={index} className="text-sm">
                <span className="font-medium text-gray-800 dark:text-gray-200">
                  {action.tool.replace(/_/g, ' ')}
                </span>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {Object.entries(action.args).map(([k, v]) => (
                    <span key={k} className="mr-3">
                      {k}: <span className="font-medium">{String(v)}</span>
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Remarks Input */}
      {interruptData.editable_fields?.includes('remarks') && (
        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">
            Remarks (optional)
          </label>
          <input
            type="text"
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            placeholder="Add any comments..."
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
            disabled={disabled}
          />
        </div>
      )}

      {/* Validation Errors */}
      {interruptData.validation_errors && interruptData.validation_errors.length > 0 && (
        <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 mb-4 border border-red-300 dark:border-red-700">
          <ul className="text-sm text-red-700 dark:text-red-300 space-y-1">
            {interruptData.validation_errors.map((error, index) => (
              <li key={index} className="flex items-center gap-2">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {error}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-3">
        {(interruptData.options?.includes('approve') || interruptData.options?.includes('confirm')) && (
          <button
            onClick={handleApprove}
            disabled={disabled}
            className="flex-1 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {approveLabel}
          </button>
        )}
        {(interruptData.options?.includes('reject') || interruptData.options?.includes('cancel')) && (
          <button
            onClick={handleReject}
            disabled={disabled}
            className="flex-1 px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            {rejectLabel}
          </button>
        )}
      </div>
    </div>
  );
};
