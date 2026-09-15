import React from 'react';
import { CheckCircle2, XCircle, RefreshCw, Hash, AlertTriangle, ArrowRight } from 'lucide-react';

export const ValidationCard = ({ fixResult, onApplyFix }) => {
  if (!fixResult) return null;

  const { success, attempts, execution_id, final_execution_id, final_error, fixed_code } = fixResult;

  const formatErrorDetail = (err) => {
    if (!err) return null;
    if (typeof err === 'string') return err;
    if (typeof err === 'object') {
      return err.message || err.detail || err.error || JSON.stringify(err, null, 2);
    }
    return String(err);
  };

  return (
    <div className={`validation-card ${success ? 'validation-success' : 'validation-failure'}`}>
      <div className="validation-header">
        <div className="validation-status">
          {success ? (
            <>
              <CheckCircle2 size={20} className="status-icon icon-success" />
              <span className="validation-title">Fix Applied Successfully</span>
            </>
          ) : (
            <>
              <XCircle size={20} className="status-icon icon-failure" />
              <span className="validation-title">Fix Validation Failed</span>
            </>
          )}
        </div>

        {success && onApplyFix && fixed_code && (
          <button
            type="button"
            className="apply-fix-btn"
            onClick={() => onApplyFix(fixed_code)}
            title="Apply this fixed code to the main code editor"
          >
            <span>Apply to Editor</span>
            <ArrowRight size={14} />
          </button>
        )}
      </div>

      <div className="validation-details flex-row">
        <div className="val-item">
          <RefreshCw size={13} className="val-icon" />
          <span className="val-label">Attempts:</span>
          <span className="val-value">{attempts}</span>
        </div>
        <div className="val-item">
          <Hash size={13} className="val-icon" />
          <span className="val-label">Execution ID:</span>
          <span className="val-value code-font">{final_execution_id || execution_id || 'N/A'}</span>
        </div>
      </div>

      {!success && final_error && (
        <div className="validation-error-block">
          <div className="error-block-title">
            <AlertTriangle size={14} />
            <span>Final Error:</span>
          </div>
          <pre className="error-text-box">{formatErrorDetail(final_error)}</pre>
        </div>
      )}
    </div>
  );
};
