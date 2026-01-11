/** Loading spinner component */

export const LoadingSpinner = () => {
  return (
    <div className="flex justify-center items-center p-4">
      <div className="relative">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 dark:border-blue-800 border-t-blue-600 dark:border-t-blue-400"></div>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-6 w-6 rounded-full bg-blue-100 dark:bg-blue-900 animate-pulse"></div>
        </div>
      </div>
    </div>
  );
};

