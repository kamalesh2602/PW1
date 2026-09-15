import React from 'react';
import { History, CheckCircle2, XCircle, ChevronRight, Clock, Trash2 } from 'lucide-react';

export const FixHistorySection = ({ history, onSelectHistoryItem, onClearHistory }) => {
  if (!history || history.length === 0) {
    return null;
  }

  return (
    <div className="fix-history-panel">
      <div className="history-header">
        <div className="history-title-group">
          <History size={16} className="history-icon" />
          <span>Fix History ({history.length})</span>
        </div>
        {onClearHistory && (
          <button
            type="button"
            className="clear-history-btn"
            onClick={onClearHistory}
            title="Clear fix history"
          >
            <Trash2 size={13} />
            <span>Clear</span>
          </button>
        )}
      </div>

      <div className="history-list">
        {history.map((item, index) => {
          const { executionId, timestamp, success, attempts } = item;
          return (
            <div
              key={index}
              className={`history-card ${success ? 'history-card-success' : 'history-card-failure'}`}
              onClick={() => onSelectHistoryItem && onSelectHistoryItem(item)}
            >
              <div className="history-card-left">
                {success ? (
                  <CheckCircle2 size={16} className="text-green" />
                ) : (
                  <XCircle size={16} className="text-red" />
                )}
                <div className="history-info">
                  <div className="history-id-row">
                    <span className="history-id">Exec ID: {executionId || 'N/A'}</span>
                    <span className="history-attempts">{attempts} attempt{attempts > 1 ? 's' : ''}</span>
                  </div>
                  <div className="history-time-row">
                    <Clock size={11} />
                    <span>{timestamp}</span>
                  </div>
                </div>
              </div>
              <ChevronRight size={16} className="history-arrow" />
            </div>
          );
        })}
      </div>
    </div>
  );
};
