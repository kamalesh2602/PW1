import React from 'react';
import { Terminal, Trash2 } from 'lucide-react';

export const InputPanel = ({ stdin, onChange, disabled }) => {
  return (
    <div className="input-panel">
      <div className="input-header">
        <div className="input-header-left">
          <Terminal size={16} />
          <span>Program Input (stdin)</span>
        </div>
        {stdin && (
          <button
            type="button"
            onClick={() => onChange('')}
            disabled={disabled}
            className="clear-input-btn"
            title="Clear stdin input"
          >
            <Trash2 size={13} />
            <span>Clear</span>
          </button>
        )}
      </div>
      <div className="input-body">
        <textarea
          value={stdin}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder={`Enter standard input for Scanner / input() here...\nExample:\n5\n10 20 30 40 50`}
          className="stdin-textarea"
          rows={3}
        />
      </div>
    </div>
  );
};
