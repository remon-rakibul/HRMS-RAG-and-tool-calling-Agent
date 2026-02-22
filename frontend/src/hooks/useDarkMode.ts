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
    const html = document.documentElement;
    const body = document.body;

    // Force update - remove all dark classes first, then add if needed
    html.classList.remove('dark');
    body.classList.remove('dark');
    if (isDark) {
      html.classList.add('dark');
    }

    localStorage.setItem('darkMode', isDark.toString());

    // Check computed styles to see if dark mode CSS is actually applied
    const testElement = document.createElement('div');
    testElement.className = 'bg-gray-50 dark:bg-gray-900';
    testElement.style.position = 'absolute';
    testElement.style.visibility = 'hidden';
    document.body.appendChild(testElement);
    const computedBg = window.getComputedStyle(testElement).backgroundColor;
    document.body.removeChild(testElement);

    // Verify the update worked
    const actualHasDark = html.classList.contains('dark');
    console.log('Dark mode updated:', isDark, 'DOM class:', actualHasDark, 'Match:', isDark === actualHasDark);
  }, [isDark]);

  const toggle = useCallback(() => {
    console.log('Toggle button clicked');
    setIsDark((prev) => {
      const newValue = !prev;
      console.log('Toggling dark mode:', prev, '->', newValue);

      // Update DOM immediately for instant feedback
      const html = document.documentElement;
      const body = document.body;

      html.classList.remove('dark');
      body.classList.remove('dark');
      if (newValue) {
        html.classList.add('dark');
      }

      localStorage.setItem('darkMode', newValue.toString());

      // Verify
      const actualHasDark = html.classList.contains('dark');
      console.log('After toggle - State:', newValue, 'DOM class:', actualHasDark);

      return newValue;
    });
  }, [isDark]);

  return { isDark, toggle, setIsDark };
};
