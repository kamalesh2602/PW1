import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { FileCode, RotateCcw, UploadCloud } from 'lucide-react';

export const CodeEditor = ({
  language,
  code,
  onChange,
  uploadedFileName,
  onResetCode,
  onFileUpload,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const monacoLanguage = language === 'python' ? 'python' : 'java';

  const editorOptions = {
    fontSize: 14,
    fontFamily: "'JetBrains Mono', Consolas, 'Courier New', monospace",
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 4,
    lineNumbers: 'on',
    renderLineHighlight: 'all',
    padding: { top: 12, bottom: 12 },
    cursorBlinking: 'smooth',
    smoothScrolling: true,
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const file = e.dataTransfer?.files?.[0];
    if (!file) return;

    const ext = file.name.split('.').pop()?.toLowerCase();
    let detectedLanguage = null;
    if (ext === 'py') detectedLanguage = 'python';
    else if (ext === 'java') detectedLanguage = 'java';

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result;
      if (typeof content === 'string' && onFileUpload) {
        onFileUpload(file.name, content, detectedLanguage);
      }
    };
    reader.readAsText(file);
  };

  const getDisplayFilename = () => {
    if (uploadedFileName) return uploadedFileName;
    if (language === 'python') return 'script.py';

    if (language === 'java' && code) {
      const cleanCode = code.replace(/\/\/.*?\n|\/\*.*?\*\//gs, '');
      const match = cleanCode.match(/\bpublic\s+(?:final\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)/) || cleanCode.match(/\bclass\s+([A-Za-z_][A-Za-z0-9_]*)/);
      if (match && match[1]) {
        return `${match[1]}.java`;
      }
    }
    return 'Main.java';
  };

  return (
    <div
      className={`editor-container ${isDragging ? 'dragging' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="editor-header">
        <div className="editor-title-group">
          <FileCode size={16} className="editor-icon" />
          <span className="editor-filename">
            {getDisplayFilename()}
          </span>
          {uploadedFileName && (
            <span className="uploaded-badge">uploaded</span>
          )}
        </div>
        <div className="editor-actions">
          {uploadedFileName && (
            <button
              onClick={onResetCode}
              className="reset-button"
              title="Reset to starter template"
            >
              <RotateCcw size={13} />
              <span>Reset</span>
            </button>
          )}
          <span className="editor-mode">{monacoLanguage.toUpperCase()}</span>
        </div>
      </div>
      <div className="editor-wrapper">
        {isDragging && (
          <div className="drag-overlay">
            <div className="drag-overlay-content">
              <UploadCloud size={40} className="drag-icon" />
              <p className="drag-title">Drop code file to load</p>
              <p className="drag-subtitle">Supports .py, .java, .txt files</p>
            </div>
          </div>
        )}
        <Editor
          height="100%"
          language={monacoLanguage}
          theme="vs-dark"
          value={code}
          onChange={(value) => onChange(value || '')}
          options={editorOptions}
        />
      </div>
    </div>
  );
};
