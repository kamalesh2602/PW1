import React, { useState } from 'react';
import Editor, { DiffEditor } from '@monaco-editor/react';
import { Columns, Code, Check, ArrowRight } from 'lucide-react';

export const DiffViewPanel = ({ originalCode, fixedCode, language, onApplyFix }) => {
  const [viewMode, setViewMode] = useState('diff'); // 'diff' or 'code'
  const monacoLanguage = language === 'python' ? 'python' : 'java';

  const editorOptions = {
    fontSize: 13,
    fontFamily: "'JetBrains Mono', Consolas, 'Courier New', monospace",
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 4,
    lineNumbers: 'on',
    readOnly: true,
    padding: { top: 12, bottom: 12 },
    renderSideBySide: true,
  };

  return (
    <div className="diff-view-panel">
      <div className="diff-header">
        <div className="diff-mode-toggle">
          <button
            type="button"
            className={`toggle-btn ${viewMode === 'diff' ? 'active' : ''}`}
            onClick={() => setViewMode('diff')}
          >
            <Columns size={14} />
            <span>Side-by-Side Diff</span>
          </button>
          <button
            type="button"
            className={`toggle-btn ${viewMode === 'code' ? 'active' : ''}`}
            onClick={() => setViewMode('code')}
          >
            <Code size={14} />
            <span>Repaired Code</span>
          </button>
        </div>

        {onApplyFix && fixedCode && (
          <button
            type="button"
            className="apply-fix-primary-btn"
            onClick={() => onApplyFix(fixedCode)}
          >
            <Check size={14} />
            <span>Apply Fix to Editor</span>
          </button>
        )}
      </div>

      <div className="diff-body">
        {viewMode === 'diff' ? (
          <div className="monaco-diff-container">
            <div className="diff-column-labels">
              <span className="diff-label label-original">Original Code (Failed)</span>
              <span className="diff-label label-fixed">Fixed Code (AI Repaired)</span>
            </div>
            <div className="diff-editor-wrapper">
              <DiffEditor
                height="100%"
                language={monacoLanguage}
                original={originalCode || ''}
                modified={fixedCode || ''}
                theme="vs-dark"
                options={editorOptions}
              />
            </div>
          </div>
        ) : (
          <div className="fixed-code-container">
            <div className="fixed-code-header">
              <span>AI-Generated Repaired Code ({monacoLanguage.toUpperCase()})</span>
            </div>
            <div className="fixed-code-editor-wrapper">
              <Editor
                height="100%"
                language={monacoLanguage}
                theme="vs-dark"
                value={fixedCode || ''}
                options={editorOptions}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
