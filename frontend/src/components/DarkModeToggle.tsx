/** Dark mode toggle button component */

import React from 'react';

interface DarkModeToggleProps {
  isDark: boolean;
  onToggle: () => void;
}

export const DarkModeToggle = ({ isDark, onToggle }: DarkModeToggleProps) => {
  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DarkModeToggle.tsx:9',message:'Component mounted/updated',data:{isDark,onToggleType:typeof onToggle},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
  }, [isDark, onToggle]);
  // #endregion

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DarkModeToggle.tsx:15',message:'handleClick called',data:{isDark,eventType:e.type},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    
    e.preventDefault();
    e.stopPropagation();
    console.log('Toggle button clicked, current isDark:', isDark);
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DarkModeToggle.tsx:22',message:'About to call onToggle',data:{isDark},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    
    onToggle();
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DarkModeToggle.tsx:25',message:'onToggle called',data:{isDark},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
  };

  // #region agent log
  React.useEffect(() => {
    const button = document.querySelector('[data-dark-toggle]');
    if (button) {
      const styles = window.getComputedStyle(button);
      fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DarkModeToggle.tsx:32',message:'Button element check',data:{exists:!!button,pointerEvents:styles.pointerEvents,zIndex:styles.zIndex,display:styles.display,visibility:styles.visibility},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    }
  }, []);
  // #endregion

  return (
    <button
      data-dark-toggle
      type="button"
      onClick={handleClick}
      className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 cursor-pointer"
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? (
        <svg
          className="w-5 h-5 text-yellow-500"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
            clipRule="evenodd"
          />
        </svg>
      ) : (
        <svg
          className="w-5 h-5 text-gray-700"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      )}
    </button>
  );
};

