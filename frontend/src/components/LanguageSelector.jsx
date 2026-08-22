import React from 'react';

export const LanguageSelector = ({ language, onLanguageChange, disabled }) => {
  return (
    <div className="language-selector-wrapper">
      <label htmlFor="language-select" className="control-label">
        Language:
      </label>
      <select
        id="language-select"
        value={language}
        onChange={(e) => onLanguageChange(e.target.value)}
        disabled={disabled}
        className="language-select"
      >
        <option value="python">Python</option>
        <option value="java">Java</option>
      </select>
    </div>
  );
};
