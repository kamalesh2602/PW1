import React from 'react';
import { AlertCircle, CheckCircle2, ShieldCheck, Sparkles, Terminal } from 'lucide-react';

export const DiagnosisPanel = ({ diagnosis }) => {
  if (!diagnosis) return null;

  const {
    diagnosis: diagnosisText,
    root_cause,
    suggested_fix,
    confidence,
    evidence,
  } = diagnosis;

  const confidencePercent = confidence !== undefined ? Math.round(confidence * 100) : null;

  return (
    <div className="diagnosis-panel">
      <div className="diagnosis-panel-header">
        <div className="diagnosis-title-group">
          <Sparkles className="sparkles-icon" size={18} />
          <span className="diagnosis-title">AI Diagnosis Report</span>
        </div>
        {confidencePercent !== null && (
          <div className={`confidence-badge ${confidencePercent >= 80 ? 'high' : 'medium'}`}>
            <ShieldCheck size={14} />
            <span>Confidence: {confidencePercent}%</span>
          </div>
        )}
      </div>

      <div className="diagnosis-panel-body">
        {/* Diagnosis Section */}
        <div className="diagnosis-block">
          <div className="block-label">
            <AlertCircle size={14} className="block-icon text-amber" />
            <span>Diagnosis</span>
          </div>
          <div className="block-divider" />
          <p className="block-text">{diagnosisText || 'No diagnosis available.'}</p>
        </div>

        {/* Root Cause Section */}
        <div className="diagnosis-block">
          <div className="block-label">
            <Terminal size={14} className="block-icon text-red" />
            <span>Root Cause</span>
          </div>
          <div className="block-divider" />
          <p className="block-text code-font">{root_cause || 'No root cause identified.'}</p>
        </div>

        {/* Suggested Fix Section */}
        <div className="diagnosis-block">
          <div className="block-label">
            <CheckCircle2 size={14} className="block-icon text-green" />
            <span>Suggested Fix</span>
          </div>
          <div className="block-divider" />
          <p className="block-text">{suggested_fix || 'No suggested fix provided.'}</p>
        </div>

        {/* Evidence Section (if available) */}
        {evidence && evidence.length > 0 && (
          <div className="diagnosis-block">
            <div className="block-label">
              <span>Evidence</span>
            </div>
            <ul className="evidence-list">
              {evidence.map((item, idx) => (
                <li key={idx} className="evidence-item">
                  <code>{item}</code>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
