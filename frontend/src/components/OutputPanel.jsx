import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Terminal,
  Wand2,
  Stethoscope,
  Loader2,
  AlertOctagon,
} from 'lucide-react';
import { DiagnosisPanel } from './DiagnosisPanel';
import { ValidationCard } from './ValidationCard';
import { DiffViewPanel } from './DiffViewPanel';

export const OutputPanel = ({
  result,
  isLoading,
  isDiagnosing,
  isFixing,
  fixStep,
  diagnosis,
  fixResult,
  fixError,
  onDiagnose,
  onFixWithAI,
  onApplyFix,
  originalCode,
  language,
}) => {
  if (isLoading) {
    return (
      <div className="output-panel loading-state">
        <div className="output-header">
          <div className="output-header-left">
            <Terminal size={18} />
            <span>Execution Output</span>
          </div>
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
          <div className="output-header-left">
            <Terminal size={18} />
            <span>Execution Output</span>
          </div>
        </div>
        <div className="output-placeholder">
          Click <strong>"Run Code"</strong> to execute code and view output.
        </div>
      </div>
    );
  }

  const { status, stdout, stderr, exit_code, execution_time, execution_id } = result;
  const isError =
    status === 'runtime_error' ||
    status === 'compile_error' ||
    status === 'execution_error' ||
    (exit_code !== null && exit_code !== 0) ||
    Boolean(stderr && stderr.trim().length > 0);

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
      {/* Panel Header */}
      <div className="output-header">
        <div className="output-header-left">
          <Terminal size={18} />
          <span>Execution Output</span>
        </div>
        {getStatusBadge()}
      </div>

      {/* Main Body */}
      <div className="output-body">
        {/* Execution Standard Output */}
        {stdout && (
          <div className="output-section stdout-section">
            <div className="section-label">stdout</div>
            <pre className="output-text">{stdout}</pre>
          </div>
        )}

        {/* Execution Error Output */}
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

        {/* Action Prompt Banner when Execution Fails */}
        {isError && (
          <div className="error-action-banner">
            <div className="error-banner-left">
              <AlertOctagon size={18} className="banner-alert-icon" />
              <div className="banner-text">
                <span className="banner-title">Runtime Error Detected</span>
                <span className="banner-sub">AI Debugger & Automatic Fixer available</span>
              </div>
            </div>

            <div className="error-banner-actions">
              <button
                type="button"
                className="action-btn diagnose-btn"
                onClick={onDiagnose}
                disabled={isDiagnosing || isFixing}
              >
                {isDiagnosing ? (
                  <>
                    <Loader2 size={14} className="spinner-icon" />
                    <span>Diagnosing...</span>
                  </>
                ) : (
                  <>
                    <Stethoscope size={14} />
                    <span>Diagnose</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="action-btn fix-ai-btn"
                onClick={onFixWithAI}
                disabled={isDiagnosing || isFixing}
              >
                {isFixing ? (
                  <>
                    <Loader2 size={14} className="spinner-icon" />
                    <span>Fixing...</span>
                  </>
                ) : (
                  <>
                    <Wand2 size={14} />
                    <span>Fix with AI</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Fix Loading State */}
        {isFixing && (
          <div className="fixing-loading-container">
            <div className="fixing-step-card">
              <Loader2 size={24} className="spinner-icon text-accent" />
              <div className="step-content">
                <div className="step-label">{fixStep || 'Processing automatic repair...'}</div>
                <div className="step-sub">Analyzing execution trace, generating patch & running tests in sandbox</div>
              </div>
            </div>
            <div className="step-indicators">
              <div className={`step-dot ${fixStep.includes('diagnosis') ? 'active' : 'done'}`}>
                1. Generating diagnosis...
              </div>
              <div className={`step-dot ${fixStep.includes('patch') ? 'active' : fixStep.includes('Validating') ? 'done' : ''}`}>
                2. Generating patch...
              </div>
              <div className={`step-dot ${fixStep.includes('Validating') ? 'active' : ''}`}>
                3. Validating fix...
              </div>
            </div>
          </div>
        )}

        {/* Fix Error Banner */}
        {fixError && (
          <div className="fix-error-banner">
            <AlertTriangle size={18} />
            <span>{fixError}</span>
          </div>
        )}

        {/* Validation Result Card */}
        {fixResult && (
          <ValidationCard fixResult={fixResult} onApplyFix={onApplyFix} />
        )}

        {/* Diagnosis Panel */}
        {diagnosis && !isFixing && (
          <DiagnosisPanel diagnosis={diagnosis} />
        )}

        {/* Repaired Code & Side-by-Side Diff View Panel */}
        {fixResult && fixResult.fixed_code && !isFixing && (
          <DiffViewPanel
            originalCode={originalCode}
            fixedCode={fixResult.fixed_code}
            language={language}
            onApplyFix={onApplyFix}
          />
        )}
      </div>

      {/* Footer Meta Details */}
      <div className="output-footer">
        {execution_id && (
          <div className="meta-item">
            <span className="meta-label">Exec ID:</span>
            <span className="meta-value code-font">{execution_id}</span>
          </div>
        )}
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
