/** Validation Card component for HITL input validation loops */

import React, { useState } from 'react';
import type { InterruptData } from '../hooks/useChat';

interface ValidationCardProps {
  interruptData: InterruptData;
  onSubmit: (data: Record<string, any>) => void;
  onCancel: () => void;
  disabled?: boolean;
}

export const ValidationCard: React.FC<ValidationCardProps> = ({
  interruptData,
  onSubmit,
  onCancel,
  disabled = false,
}) => {
  const [values, setValues] = useState<Record<string, any>>(
    interruptData.current_values || {}
  );

  const handleValueChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleConfirm = () => {
    onSubmit({
      action: 'confirm',
      ...values,
    });
  };

  const handleEdit = () => {
    onSubmit({
      action: 'edit',
      ...values,
    });
  };

  // If resolved, show a simple resolved state
  if (interruptData.resolved) {
    return (
      <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 border border-gray-300 dark:border-gray-600 opacity-60 max-w-md mx-auto">
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-sm">Input validated</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-5 border-2 border-blue-400 dark:border-blue-500 shadow-lg max-w-md mx-auto">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 bg-blue-100 dark:bg-blue-800 rounded-full flex-shrink-0">
          <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-blue-800 dark:text-blue-200 text-lg">
            Input Validation
          </h3>
          <p className="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-wide">
            {interruptData.action.replace(/_/g, ' ')}
          </p>
        </div>
      </div>

      {/* Message */}
      <p className="text-gray-800 dark:text-gray-200 mb-4 text-sm leading-relaxed">
        {interruptData.message}
      </p>

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

      {/* Editable Fields */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4 border border-gray-200 dark:border-gray-700 space-y-4">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-3">
          Edit Values
        </span>
        
        {Object.entries(values).map(([key, value]) => (
          <div key={key}>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 capitalize">
              {key.replace(/_/g, ' ')}
            </label>
            <input
              type="text"
              value={String(value)}
              onChange={(e) => handleValueChange(key, e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-gray-200 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              disabled={disabled}
            />
          </div>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        {interruptData.options?.includes('confirm') && (
          <button
            onClick={handleConfirm}
            disabled={disabled}
            className="flex-1 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Confirm
          </button>
        )}
        {interruptData.options?.includes('edit') && (
          <button
            onClick={handleEdit}
            disabled={disabled}
            className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Save Changes
          </button>
        )}
        {interruptData.options?.includes('cancel') && (
          <button
            onClick={onCancel}
            disabled={disabled}
            className="flex-1 px-4 py-2.5 bg-gray-500 hover:bg-gray-600 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
};
