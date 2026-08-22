import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Clock, Terminal } from 'lucide-react';

export const OutputPanel = ({ result, isLoading }) => {
  if (isLoading) {
    return (
      <div className="output-panel loading-state">
        <div className="output-header">
          <Terminal size={18} />
          <span>Execution Output</span>
        </div>
        <div className="output-placeholder">
          <div className="pulse-loader">Running program in Docker sandbox...</div>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="output-panel empty-state">
        <div className="output-header">
          <Terminal size={18} />
          <span>Execution Output</span>
        </div>
        <div className="output-placeholder">
          Click <strong>"Run Code"</strong> to execute code and view output.
        </div>
      </div>
    );
  }

  const { status, stdout, stderr, exit_code, execution_time } = result;

  const getStatusBadge = () => {
    switch (status) {
      case 'success':
        return (
          <div className="status-badge status-success">
            <CheckCircle2 size={16} />
            <span>Status: Success</span>
          </div>
        );
      case 'compile_error':
        return (
          <div className="status-badge status-compile-error">
            <AlertTriangle size={16} />
            <span>Status: Compilation Error</span>
          </div>
        );
      case 'runtime_error':
        return (
          <div className="status-badge status-runtime-error">
            <XCircle size={16} />
            <span>Status: Runtime Error</span>
          </div>
        );
      case 'timeout':
        return (
          <div className="status-badge status-timeout">
            <Clock size={16} />
            <span>Status: Timeout</span>
          </div>
        );
      case 'execution_error':
      default:
        return (
          <div className="status-badge status-execution-error">
            <AlertTriangle size={16} />
            <span>Status: Execution Error</span>
          </div>
        );
    }
  };

  return (
    <div className="output-panel">
      <div className="output-header">
        <div className="output-header-left">
          <Terminal size={18} />
          <span>Execution Output</span>
        </div>
        {getStatusBadge()}
      </div>

      <div className="output-body">
        {stdout && (
          <div className="output-section stdout-section">
            <div className="section-label">stdout</div>
            <pre className="output-text">{stdout}</pre>
          </div>
        )}

        {stderr && (
          <div className="output-section stderr-section">
            <div className="section-label">stderr</div>
            <pre className="output-text error-text">{stderr}</pre>
          </div>
        )}

        {!stdout && !stderr && (
          <div className="output-section">
            <pre className="output-text muted-text">[Program finished with no output]</pre>
          </div>
        )}
      </div>

      <div className="output-footer">
        <div className="meta-item">
          <span className="meta-label">Execution time:</span>
          <span className="meta-value">{execution_time !== null ? `${execution_time}s` : 'N/A'}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Exit code:</span>
          <span className="meta-value">{exit_code !== null ? exit_code : 'N/A'}</span>
        </div>
      </div>
    </div>
  );
};
