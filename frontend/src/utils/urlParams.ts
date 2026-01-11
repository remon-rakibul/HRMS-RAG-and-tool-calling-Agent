/** URL parameter parsing utilities */

export const getUrlParam = (param: string): string | null => {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(param);
};

export const getSessionId = (): string | null => {
  return getUrlParam('sessionId');
};

