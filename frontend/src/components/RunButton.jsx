import React from 'react';
import { Play, Loader2 } from 'lucide-react';

export const RunButton = ({ onRun, isLoading }) => {
  return (
    <button
      onClick={onRun}
      disabled={isLoading}
      className={`run-button ${isLoading ? 'loading' : ''}`}
    >
      {isLoading ? (
        <>
          <Loader2 className="spinner-icon" size={16} />
          <span>Running...</span>
        </>
      ) : (
        <>
          <Play size={16} fill="currentColor" />
          <span>Run Code</span>
        </>
      )}
    </button>
  );
};
