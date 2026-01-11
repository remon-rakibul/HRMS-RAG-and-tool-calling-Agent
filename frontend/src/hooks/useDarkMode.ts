/** Dark mode hook */

import { useState, useEffect, useCallback } from 'react';

// Get initial dark mode state - check actual DOM state first
const getInitialDarkMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  
  // First, check if dark class is already on the document (from index.html script)
  const html = document.documentElement;
  const hasDarkClass = html.classList.contains('dark');
  
  // Check localStorage
  const stored = localStorage.getItem('darkMode');
  
  // If localStorage has a value, use it (but sync DOM)
  if (stored === 'true') {
      html.classList.add('dark');
      return true;
  }
  if (stored === 'false') {
      html.classList.remove('dark');
      return false;
  }
  
  // If no localStorage, use the actual DOM state (from index.html script)
  // This ensures we match what's actually rendered
  return hasDarkClass;
};

export const useDarkMode = () => {
  const [isDark, setIsDark] = useState(() => {
    const initial = getInitialDarkMode();
    console.log('Initial dark mode state:', initial, 'DOM has dark class:', document.documentElement.classList.contains('dark'));
    return initial;
  });

  // Update DOM and localStorage when state changes
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:39',message:'useEffect triggered',data:{isDark,htmlClasses:document.documentElement.className,bodyClasses:document.body.className},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    const html = document.documentElement;
    const body = document.body;
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:45',message:'Before DOM update',data:{htmlHasDark:html.classList.contains('dark'),bodyHasDark:body.classList.contains('dark'),htmlClassList:Array.from(html.classList),bodyClassList:Array.from(body.classList)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    // Force update - remove all dark classes first, then add if needed
    html.classList.remove('dark');
    body.classList.remove('dark');
    if (isDark) {
      html.classList.add('dark');
    }
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:55',message:'After DOM update',data:{htmlHasDark:html.classList.contains('dark'),bodyHasDark:body.classList.contains('dark'),htmlClassList:Array.from(html.classList),bodyClassList:Array.from(body.classList)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    localStorage.setItem('darkMode', isDark.toString());
    
    // Check computed styles to see if dark mode CSS is actually applied
    const testElement = document.createElement('div');
    testElement.className = 'bg-gray-50 dark:bg-gray-900';
    testElement.style.position = 'absolute';
    testElement.style.visibility = 'hidden';
    document.body.appendChild(testElement);
    const computedBg = window.getComputedStyle(testElement).backgroundColor;
    document.body.removeChild(testElement);
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:70',message:'Computed style check',data:{isDark,htmlHasDark:html.classList.contains('dark'),testElementBg:computedBg,expectedDarkBg:'rgb(17, 24, 39)',expectedLightBg:'rgb(249, 250, 251)'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    
    // Verify the update worked
    const actualHasDark = html.classList.contains('dark');
    console.log('Dark mode updated:', isDark, 'DOM class:', actualHasDark, 'Match:', isDark === actualHasDark);
  }, [isDark]);

  const toggle = useCallback(() => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:78',message:'Toggle clicked',data:{currentIsDark:isDark,htmlHasDark:document.documentElement.classList.contains('dark')},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    
    console.log('Toggle button clicked');
    setIsDark((prev) => {
      const newValue = !prev;
      console.log('Toggling dark mode:', prev, '->', newValue);
      
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:85',message:'Inside toggle setState',data:{prev,newValue},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      
      // Update DOM immediately for instant feedback
      const html = document.documentElement;
      const body = document.body;
      
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:92',message:'Before toggle DOM update',data:{newValue,htmlHasDark:html.classList.contains('dark'),bodyHasDark:body.classList.contains('dark')},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      html.classList.remove('dark');
      body.classList.remove('dark');
      if (newValue) {
        html.classList.add('dark');
      }
      
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/914ce8e7-e2d2-4072-91c7-98c052f8c9b6',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useDarkMode.ts:100',message:'After toggle DOM update',data:{newValue,htmlHasDark:html.classList.contains('dark'),bodyHasDark:body.classList.contains('dark'),htmlClassList:Array.from(html.classList)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      localStorage.setItem('darkMode', newValue.toString());
      
      // Verify
      const actualHasDark = html.classList.contains('dark');
      console.log('After toggle - State:', newValue, 'DOM class:', actualHasDark);
      
      return newValue;
    });
  }, [isDark]); // Include isDark to log current state

  return { isDark, toggle, setIsDark };
};
