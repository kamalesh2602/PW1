import React, { useState, useEffect, useRef } from 'react';
import {
  FlaskConical,
  Play,
  Layers,
  Sparkles,
  Database,
  Clock,
  Cpu,
  CheckCircle2,
  XCircle,
  TrendingDown,
  RefreshCw,
  ChevronRight,
  Download,
  Eye,
  X,
  Copy,
  Check,
  Terminal,
  Activity,
  AlertTriangle,
  Info,
  Trash2,
} from 'lucide-react';
import {
  getBenchmarks,
  runPairedEvaluation,
  getRecentExperiments,
  getExportCsvUrl,
  getExperimentSummary,
  getExperimentEvents,
  clearEvaluationResults,
} from '../services/evaluationService';
import { getFriendlyErrorMessage, AI_UNAVAILABLE_MESSAGE } from '../utils/errorUtils';

// Helper function to format reduction honestly without misleading negative signs
const formatReduction = (percent, isToken = false) => {
  if (percent === null || percent === undefined || isNaN(percent)) {
    return 'N/A';
  }
  const val = Number(percent);
  if (val > 0) {
    return `${val.toFixed(1)}% reduction`;
  } else if (val < 0) {
    return `+${Math.abs(val).toFixed(1)}% increased usage`;
  }
  return '0.0% (no change)';
};

// Helper function for concise table reduction column
const formatTableReduction = (percent) => {
  if (percent === null || percent === undefined || isNaN(percent) || percent === 0) {
    return '-';
  }
  const val = Number(percent);
  if (val > 0) {
    return `${val.toFixed(1)}%`;
  }
  return `+${Math.abs(val).toFixed(1)}%`;
};

export const EvaluationSection = ({ onLoadBenchmarkCode }) => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [selectedBugId, setSelectedBugId] = useState('B001');
  const [isRunning, setIsRunning] = useState(false);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [evalError, setEvalError] = useState(null);
  const [recentExperiments, setRecentExperiments] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Inspection states
  const inspectorRef = useRef(null);
  const [selectedEvaluationId, setSelectedEvaluationId] = useState(null);
  const [inspectedRecord, setInspectedRecord] = useState(null);
  const [inspectionSummary, setInspectionSummary] = useState(null);
  const [inspectionEvents, setInspectionEvents] = useState([]);
  const [isLoadingInspection, setIsLoadingInspection] = useState(false);
  const [inspectionError, setInspectionError] = useState(null);
  const [activeInspectTab, setActiveInspectTab] = useState('summary');
  const [copied, setCopied] = useState(false);

  // Clear Results states
  const [isClearModalOpen, setIsClearModalOpen] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [clearStatusMessage, setClearStatusMessage] = useState(null);

  const handleOpenClearModal = () => {
    if (isRunning || isClearing) return;
    setIsClearModalOpen(true);
  };

  const handleCloseClearModal = () => {
    if (isClearing) return;
    setIsClearModalOpen(false);
  };

  const handleConfirmClear = async () => {
    if (isClearing || isRunning) return;
    setIsClearing(true);
    setClearStatusMessage(null);

    try {
      const res = await clearEvaluationResults();
      if (res && res.success) {
        // Immediately reset all frontend result & inspection states to empty state
        setRecentExperiments([]);
        setComparisonResult(null);
        setSelectedEvaluationId(null);
        setInspectedRecord(null);
        setInspectionSummary(null);
        setInspectionEvents([]);
        setInspectionError(null);

        setClearStatusMessage({
          type: 'success',
          text: res.message || 'All M8 experiment results and generated artifacts successfully cleared.',
        });

        setIsClearModalOpen(false);
        fetchHistory();
      } else {
        setClearStatusMessage({
          type: 'error',
          text: res?.message || 'Encountered an issue clearing some M8 artifacts.',
        });
        setIsClearModalOpen(false);
        fetchHistory();
      }
    } catch (err) {
      console.error('Failed to clear M8 results:', err);
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Failed to clear M8 experiment results. Please try again.';
      setClearStatusMessage({
        type: 'error',
        text: detail,
      });
      setIsClearModalOpen(false);
    } finally {
      setIsClearing(false);
    }
  };

  useEffect(() => {
    fetchBenchmarks();
    fetchHistory();
  }, []);

  const fetchBenchmarks = async () => {
    try {
      const data = await getBenchmarks();
      setBenchmarks(data);
      if (data.length > 0 && !selectedBugId) {
        setSelectedBugId(data[0].bug_id);
      }
    } catch (err) {
      console.error('Failed to load benchmarks:', err);
    }
  };

  const fetchHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const data = await getRecentExperiments(30);
      setRecentExperiments(data);
    } catch (err) {
      console.error('Failed to load experiments history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleRunPaired = async () => {
    setIsRunning(true);
    setEvalError(null);
    try {
      const res = await runPairedEvaluation({ bugId: selectedBugId });
      setComparisonResult(res);
      fetchHistory();
      // Automatically load the inspection for the newly completed evaluation
      if (res && res.evaluation_id) {
        handleInspectEvaluation(res.evaluation_id);
      }
    } catch (err) {
      setEvalError(getFriendlyErrorMessage(err, AI_UNAVAILABLE_MESSAGE));
    } finally {
      setIsRunning(false);
    }
  };

  const handleInspectEvaluation = async (evalId, expRecord = null) => {
    const targetId = evalId || expRecord?.evaluation_id || expRecord?.experiment_id;
    if (!targetId || targetId === '-') return;

    setSelectedEvaluationId(targetId);
    setInspectedRecord(expRecord);
    setIsLoadingInspection(true);
    setInspectionError(null);

    // Scroll inspector card smoothly into view
    setTimeout(() => {
      inspectorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 60);

    try {
      const [sumRes, evRes] = await Promise.allSettled([
        getExperimentSummary(targetId),
        getExperimentEvents(targetId),
      ]);

      let hasArtifactData = false;

      if (sumRes.status === 'fulfilled' && sumRes.value) {
        setInspectionSummary(sumRes.value);
        hasArtifactData = true;
      } else {
        setInspectionSummary(null);
      }

      if (evRes.status === 'fulfilled' && Array.isArray(evRes.value)) {
        setInspectionEvents(evRes.value);
        if (evRes.value.length > 0) {
          hasArtifactData = true;
        }
      } else {
        setInspectionEvents([]);
      }

      if (!hasArtifactData) {
        const errorDetail =
          sumRes.reason?.response?.data?.detail ||
          sumRes.reason?.message ||
          `No artifact files or summary found for '${targetId}'.`;
        setInspectionError(errorDetail);
      }
    } catch (err) {
      console.error('Failed to load evaluation inspection:', err);
      setInspectionError(err.response?.data?.detail || err.message || 'Failed to retrieve experiment details.');
    } finally {
      setIsLoadingInspection(false);
    }
  };

  const handleCopyId = (id) => {
    if (!id) return;
    navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const selectedBench = benchmarks.find((b) => b.bug_id === selectedBugId);

  return (
    <div className="evaluation-container">
      {/* 1. Page Header */}
      <div className="evaluation-header">
        <div className="evaluation-header-left">
          <FlaskConical size={20} className="text-accent" />
          <div>
            <h3 className="evaluation-title">Benchmark Evaluation & Baseline Comparison</h3>
            <p className="evaluation-subtitle">
              Evaluating <strong>Baseline (Full Context)</strong> vs <strong>Dynamic (Curated Context via MCP)</strong> on controlled benchmarks
            </p>
          </div>
        </div>
        <div className="evaluation-header-actions">
          <a
            href={getExportCsvUrl()}
            download="m8_experiments.csv"
            className="action-btn export-csv-btn"
            title="Download full evaluation dataset (CSV)"
          >
            <Download size={14} />
            <span>Export CSV</span>
          </a>
          <button
            type="button"
            className="history-refresh-btn"
            onClick={fetchHistory}
            title="Refresh experiment records"
          >
            <RefreshCw size={14} className={isLoadingHistory ? 'spin-icon' : ''} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            id="clear-results-btn"
            className="action-btn clear-results-btn"
            onClick={handleOpenClearModal}
            disabled={isClearing || isRunning}
            title="Clear all saved M8 experiment results and generated artifacts"
          >
            {isClearing ? (
              <>
                <RefreshCw size={14} className="spin-icon" />
                <span>Clearing...</span>
              </>
            ) : (
              <>
                <Trash2 size={14} />
                <span>Clear Results</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Clear Status Message Banner */}
      {clearStatusMessage && (
        <div
          id="clear-status-banner"
          className={`clear-status-banner ${clearStatusMessage.type === 'success' ? 'status-banner-success' : 'status-banner-error'}`}
        >
          <div className="banner-content">
            {clearStatusMessage.type === 'success' ? (
              <CheckCircle2 size={16} className="text-success" />
            ) : (
              <AlertTriangle size={16} className="text-error" />
            )}
            <span>{clearStatusMessage.text}</span>
          </div>
          <button
            type="button"
            className="clear-banner-close-btn"
            onClick={() => setClearStatusMessage(null)}
            title="Dismiss message"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* 2. Experiment Controls / Benchmark Picker */}
      <div className="eval-toolbar">
        <div className="benchmark-picker">
          <label htmlFor="benchmark-select" className="eval-label">Benchmark Task:</label>
          <select
            id="benchmark-select"
            className="benchmark-dropdown"
            value={selectedBugId}
            onChange={(e) => setSelectedBugId(e.target.value)}
            disabled={isRunning}
          >
            {benchmarks.map((b) => (
              <option key={b.bug_id} value={b.bug_id}>
                {b.bug_id}: {b.title} ({b.expected_error})
              </option>
            ))}
          </select>
        </div>

        {selectedBench && onLoadBenchmarkCode && (
          <button
            type="button"
            className="action-btn secondary-btn load-code-btn"
            onClick={() => onLoadBenchmarkCode(selectedBench.code, selectedBench.language)}
            title="Load this benchmark code into the editor"
          >
            <ChevronRight size={14} />
            <span>Load Code into Editor</span>
          </button>
        )}

        <button
          type="button"
          className="action-btn primary-btn run-eval-btn"
          onClick={handleRunPaired}
          disabled={isRunning}
        >
          {isRunning ? (
            <>
              <RefreshCw size={14} className="spin-icon" />
              <span>Evaluating Paired Runs...</span>
            </>
          ) : (
            <>
              <Play size={14} />
              <span>Run Paired Evaluation</span>
            </>
          )}
        </button>
      </div>

      {/* Loading state indicator */}
      {isRunning && (
        <div className="eval-running-banner">
          <RefreshCw size={16} className="spin-icon" />
          <div className="eval-running-text">
            <strong>Evaluation in progress...</strong>
            <span>Executing paired experiments (Baseline vs Dynamic via MCP) on benchmark {selectedBugId}. Capturing runtime evaluation telemetry.</span>
          </div>
        </div>
      )}

      {/* 3. Selected Benchmark Information */}
      {selectedBench && (
        <div className="benchmark-card">
          <div className="bench-meta">
            <span className="badge category-badge">{selectedBench.category || selectedBench.bug_category}</span>
            <span className="badge error-badge">{selectedBench.expected_error || selectedBench.expected_failure}</span>
            <span className="badge lang-badge">{selectedBench.language}</span>
          </div>
          <p className="bench-desc">{selectedBench.description}</p>
          {(selectedBench.expected_root_cause || selectedBench.expected_behavior) && (
            <div className="bench-details-grid">
              {selectedBench.expected_root_cause && (
                <div className="bench-detail-item">
                  <span className="bench-detail-label">Expected Root Cause:</span>
                  <span className="bench-detail-value">{selectedBench.expected_root_cause}</span>
                </div>
              )}
              {selectedBench.expected_behavior && (
                <div className="bench-detail-item">
                  <span className="bench-detail-label">Expected Behavior:</span>
                  <span className="bench-detail-value">{selectedBench.expected_behavior}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {evalError && (
        <div className="eval-error-banner">
          <XCircle size={16} />
          <span>{evalError}</span>
        </div>
      )}

      {/* 4. Baseline vs Dynamic Side-by-Side Comparison */}
      {comparisonResult && (
        <div className="comparison-card">
          <div className="comparison-card-header">
            <div>
              <h4>Experimental Comparison — Benchmark {comparisonResult.bug_id}</h4>
              <span className="text-xs text-muted font-mono">Evaluation ID: {comparisonResult.evaluation_id}</span>
            </div>
            <div className="comparison-header-actions">
              <button
                type="button"
                className="action-btn inspect-eval-btn"
                onClick={() => handleInspectEvaluation(comparisonResult.evaluation_id)}
                title="Inspect detailed artifacts and event logs"
              >
                <Eye size={13} />
                <span>Inspect Artifacts</span>
              </button>
              <div className="reduction-pill">
                <TrendingDown size={14} />
                <span>
                  Context Character Reduction:{' '}
                  {formatReduction(comparisonResult.context_reduction_percent)}
                </span>
              </div>
            </div>
          </div>

          <div className="comparison-kpi-grid">
            <div className="kpi-card">
              <span className="kpi-label">Context Character Reduction</span>
              <div className={`kpi-value ${comparisonResult.context_reduction_percent > 0 ? 'text-reduction' : comparisonResult.context_reduction_percent < 0 ? 'text-increase' : ''}`}>
                {formatReduction(comparisonResult.context_reduction_percent)}
              </div>
              <span className="kpi-sub">
                {(comparisonResult.dynamic.context_chars ?? 0).toLocaleString()} vs {(comparisonResult.baseline.context_chars ?? 0).toLocaleString()} chars
              </span>
            </div>

            <div className="kpi-card">
              <span className="kpi-label">Total Token Impact</span>
              <div className={`kpi-value ${comparisonResult.token_reduction_percent > 0 ? 'text-reduction' : comparisonResult.token_reduction_percent < 0 ? 'text-increase' : ''}`}>
                {formatReduction(comparisonResult.token_reduction_percent, true)}
              </div>
              <span className="kpi-sub">
                {comparisonResult.dynamic.token_usage_available && comparisonResult.baseline.token_usage_available
                  ? `${(comparisonResult.dynamic.total_tokens ?? 0).toLocaleString()} vs ${(comparisonResult.baseline.total_tokens ?? 0).toLocaleString()} total tokens`
                  : 'Provider metadata unavailable'}
              </span>
            </div>

            <div className="kpi-card">
              <span className="kpi-label">LLM Input Tokens</span>
              <div className="kpi-value">
                {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.input_tokens !== null
                  ? `${comparisonResult.dynamic.input_tokens.toLocaleString()} tokens`
                  : 'N/A'}
              </div>
              <span className="kpi-sub">
                {comparisonResult.baseline.token_usage_available && comparisonResult.baseline.input_tokens !== null
                  ? `Baseline: ${comparisonResult.baseline.input_tokens.toLocaleString()} tokens`
                  : 'Provider metadata unavailable'}
              </span>
            </div>

            <div className="kpi-card">
              <span className="kpi-label">Debugging Effectiveness</span>
              <div className="kpi-value">
                {comparisonResult.dynamic.fix_correct === true ? (
                  <span className="text-success flex-row items-center gap-1">
                    <CheckCircle2 size={16} /> Validated
                  </span>
                ) : comparisonResult.dynamic.fix_correct === false ? (
                  <span className="text-error flex-row items-center gap-1">
                    <XCircle size={16} /> Failed
                  </span>
                ) : comparisonResult.dynamic.re_execution_passed ? (
                  <span className="text-warning flex-row items-center gap-1">
                    Passed (Exit 0)
                  </span>
                ) : (
                  <span className="text-error flex-row items-center gap-1">
                    <XCircle size={16} /> Needs Review
                  </span>
                )}
              </div>
              <span className="kpi-sub">
                Root Cause: {comparisonResult.dynamic.root_cause_identified ? 'Yes' : 'No'} • Re-exec: {comparisonResult.dynamic.re_execution_passed ? 'Pass' : 'Fail'}
              </span>
            </div>
          </div>

          <div className="comparison-table-wrapper">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Evaluation Metric</th>
                  <th className="th-baseline">Baseline (Full Context)</th>
                  <th className="th-dynamic">Dynamic (Curated Context)</th>
                  <th className="th-diff">Difference / Observation</th>
                </tr>
              </thead>
              <tbody>
                {/* Group A: Context Efficiency */}
                <tr className="table-group-header">
                  <td colSpan={4}>A. Context Efficiency</td>
                </tr>
                <tr>
                  <td className="metric-name">Status</td>
                  <td>
                    <span className={`outcome-pill ${comparisonResult.baseline.status === 'completed' ? 'success' : 'failure'}`}>
                      {comparisonResult.baseline.status === 'completed' ? 'Completed' : comparisonResult.baseline.status}
                    </span>
                  </td>
                  <td>
                    <span className={`outcome-pill ${comparisonResult.dynamic.status === 'completed' ? 'success' : 'failure'}`}>
                      {comparisonResult.dynamic.status === 'completed' ? 'Completed' : comparisonResult.dynamic.status}
                    </span>
                  </td>
                  <td>Run execution status</td>
                </tr>
                <tr>
                  <td className="metric-name">
                    Context Size (characters)
                    <span className="block text-xs text-muted font-normal">Payload chars provided to diagnosis prompt</span>
                  </td>
                  <td>{(comparisonResult.baseline.context_chars ?? comparisonResult.baseline.context_size ?? 0).toLocaleString()} chars</td>
                  <td>{(comparisonResult.dynamic.context_chars ?? comparisonResult.dynamic.context_size ?? 0).toLocaleString()} chars</td>
                  <td className={comparisonResult.context_reduction_percent > 0 ? 'text-reduction' : comparisonResult.context_reduction_percent < 0 ? 'text-increase' : ''}>
                    {formatReduction(comparisonResult.context_reduction_percent)}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">
                    Actual LLM Input Tokens
                    <span className="block text-xs text-muted font-normal">Prompt tokens sent to provider</span>
                  </td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.baseline.input_tokens !== null
                      ? `${comparisonResult.baseline.input_tokens.toLocaleString()} tokens`
                      : 'N/A — provider metadata unavailable'}
                  </td>
                  <td>
                    {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.input_tokens !== null
                      ? `${comparisonResult.dynamic.input_tokens.toLocaleString()} tokens (Curator: ${comparisonResult.dynamic.curator_input_tokens ?? 0}, Debugger: ${comparisonResult.dynamic.debugger_input_tokens ?? 0})`
                      : 'N/A — provider metadata unavailable'}
                  </td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.dynamic.token_usage_available && comparisonResult.baseline.input_tokens && comparisonResult.dynamic.input_tokens
                      ? formatReduction(((comparisonResult.baseline.input_tokens - comparisonResult.dynamic.input_tokens) / comparisonResult.baseline.input_tokens) * 100, true)
                      : 'Prompt tokens sent to provider'}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">
                    Actual LLM Output Tokens
                    <span className="block text-xs text-muted font-normal">Completion tokens generated by provider</span>
                  </td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.baseline.output_tokens !== null
                      ? `${comparisonResult.baseline.output_tokens.toLocaleString()} tokens`
                      : 'N/A — provider metadata unavailable'}
                  </td>
                  <td>
                    {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.output_tokens !== null
                      ? `${comparisonResult.dynamic.output_tokens.toLocaleString()} tokens (Curator: ${comparisonResult.dynamic.curator_output_tokens ?? 0}, Debugger: ${comparisonResult.dynamic.debugger_output_tokens ?? 0})`
                      : 'N/A — provider metadata unavailable'}
                  </td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.dynamic.token_usage_available && comparisonResult.baseline.output_tokens !== null && comparisonResult.dynamic.output_tokens !== null
                      ? `Dynamic: +${Math.max(0, (comparisonResult.dynamic.output_tokens - comparisonResult.baseline.output_tokens)).toLocaleString()} tokens`
                      : 'Completion tokens generated'}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">
                    Total LLM Tokens
                    <span className="block text-xs text-muted font-normal">Aggregate provider tokens (Input + Output)</span>
                  </td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.baseline.total_tokens !== null
                      ? `${comparisonResult.baseline.total_tokens.toLocaleString()} tokens (In: ${comparisonResult.baseline.input_tokens ?? 0} + Out: ${comparisonResult.baseline.output_tokens ?? 0})`
                      : 'N/A — provider metadata unavailable'}
                  </td>
                  <td>
                    {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.total_tokens !== null
                      ? `${comparisonResult.dynamic.total_tokens.toLocaleString()} tokens (Curator: ${comparisonResult.dynamic.curator_total_tokens ?? 0}, Debugger: ${comparisonResult.dynamic.debugger_total_tokens ?? 0})`
                      : 'N/A — provider metadata unavailable'}
                  </td>
                  <td>
                    {comparisonResult.token_reduction_percent !== null
                      ? formatReduction(comparisonResult.token_reduction_percent, true)
                      : 'N/A (provider metadata unavailable)'}
                  </td>
                </tr>

                {/* Group B: Execution Overhead */}
                <tr className="table-group-header">
                  <td colSpan={4}>B. Execution Overhead</td>
                </tr>
                <tr>
                  <td className="metric-name">Total LLM Calls</td>
                  <td>{comparisonResult.baseline.llm_calls} call</td>
                  <td>{comparisonResult.dynamic.llm_calls} calls</td>
                  <td>
                    {comparisonResult.dynamic.llm_calls > comparisonResult.baseline.llm_calls
                      ? `+${comparisonResult.dynamic.llm_calls - comparisonResult.baseline.llm_calls} call (Curator step)`
                      : 'Identical count'}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">Total MCP Calls</td>
                  <td>0 calls (Direct Context)</td>
                  <td>{comparisonResult.dynamic.mcp_calls} calls (Selective Retrieval)</td>
                  <td>Dynamic MCP tool queries</td>
                </tr>
                <tr>
                  <td className="metric-name">
                    Total Experiment Time (ms)
                    <span className="block text-xs text-muted font-normal">End-to-end wall-clock time</span>
                  </td>
                  <td>{(comparisonResult.baseline.total_experiment_time_ms || 0).toFixed(1)} ms</td>
                  <td>{(comparisonResult.dynamic.total_experiment_time_ms || 0).toFixed(1)} ms</td>
                  <td>
                    {comparisonResult.time_difference_ms > 0
                      ? `+${comparisonResult.time_difference_ms.toFixed(1)} ms`
                      : `${comparisonResult.time_difference_ms.toFixed(1)} ms`}
                  </td>
                </tr>

                {/* Group C: Debugging Effectiveness */}
                <tr className="table-group-header">
                  <td colSpan={4}>C. Debugging Effectiveness</td>
                </tr>
                <tr>
                  <td className="metric-name">Root Cause Identified</td>
                  <td>
                    {comparisonResult.baseline.root_cause_identified ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Yes</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> No</span>
                    )}
                  </td>
                  <td>
                    {comparisonResult.dynamic.root_cause_identified ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Yes</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> No</span>
                    )}
                  </td>
                  <td>Root cause diagnosis outcome</td>
                </tr>
                <tr>
                  <td className="metric-name">Re-execution Passed</td>
                  <td>
                    {comparisonResult.baseline.re_execution_passed ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Passed</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> Failed</span>
                    )}
                  </td>
                  <td>
                    {comparisonResult.dynamic.re_execution_passed ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Passed</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> Failed</span>
                    )}
                  </td>
                  <td>Sandbox exit code 0</td>
                </tr>
                <tr>
                  <td className="metric-name">Fix Correct</td>
                  <td>
                    {comparisonResult.baseline.fix_correct === true ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Validated</span>
                    ) : comparisonResult.baseline.fix_correct === false ? (
                      <span className="outcome-pill failure"><XCircle size={12} /> Failed</span>
                    ) : (
                      <span className="outcome-pill neutral">Not Validated</span>
                    )}
                  </td>
                  <td>
                    {comparisonResult.dynamic.fix_correct === true ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Validated</span>
                    ) : comparisonResult.dynamic.fix_correct === false ? (
                      <span className="outcome-pill failure"><XCircle size={12} /> Failed</span>
                    ) : (
                      <span className="outcome-pill neutral">Not Validated</span>
                    )}
                  </td>
                  <td>Deterministic semantic check</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. Detailed Research Run Inspector (Expandable Modal / Card) */}
      {selectedEvaluationId && (
        <div ref={inspectorRef} id="research-inspector" className="evaluation-inspector-card">
          <div className="inspector-header">
            <div className="inspector-header-left">
              <Layers size={18} className="text-accent" />
              <div>
                <h4>Research Artifact Inspector</h4>
                <div className="inspector-id-row">
                  <span className="font-mono text-xs text-muted">Evaluation ID: {selectedEvaluationId}</span>
                  {inspectedRecord?.experiment_id && inspectedRecord.experiment_id !== selectedEvaluationId && (
                    <span className="font-mono text-xs text-muted">| Exp: {inspectedRecord.experiment_id.slice(-16)}</span>
                  )}
                  {inspectedRecord?.bug_id && (
                    <span className="badge category-badge">{inspectedRecord.bug_id}</span>
                  )}
                  {inspectedRecord?.mode && (
                    <span className={`mode-badge ${inspectedRecord.mode}`}>{inspectedRecord.mode}</span>
                  )}
                  <button
                    type="button"
                    className="copy-id-btn"
                    onClick={() => handleCopyId(selectedEvaluationId)}
                    title="Copy Evaluation ID to clipboard"
                  >
                    {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
              </div>
            </div>
            <button
              type="button"
              className="close-inspector-btn"
              onClick={() => {
                setSelectedEvaluationId(null);
                setInspectionError(null);
                setInspectedRecord(null);
              }}
              title="Close Inspector"
            >
              <X size={16} />
            </button>
          </div>

          {/* Traceability Location Banner */}
          <div className="inspector-trace-banner">
            <div className="trace-path-info">
              <span className="trace-label">Experiment Artifact Storage:</span>
              <code className="trace-path">experiments/{selectedEvaluationId}/</code>
            </div>
            <div className="trace-files-list">
              <span className="trace-file-tag">events.jsonl</span>
              <span className="trace-file-tag">summary.json</span>
              <span className="trace-file-tag">baseline.json</span>
              <span className="trace-file-tag">dynamic.json</span>
            </div>
          </div>

          {/* Error Alert if artifacts failed to load */}
          {inspectionError && (
            <div className="eval-error-banner" style={{ margin: '4px 0' }}>
              <AlertTriangle size={16} />
              <span>{inspectionError}</span>
            </div>
          )}

          {/* Inspector Tabs */}
          <div className="inspector-tabs">
            <button
              type="button"
              className={`inspector-tab ${activeInspectTab === 'summary' ? 'active' : ''}`}
              onClick={() => setActiveInspectTab('summary')}
            >
              <Sparkles size={14} />
              <span>Experiment Summary</span>
            </button>
            <button
              type="button"
              className={`inspector-tab ${activeInspectTab === 'events' ? 'active' : ''}`}
              onClick={() => setActiveInspectTab('events')}
            >
              <Activity size={14} />
              <span>Lifecycle Events ({inspectionEvents?.length || 0})</span>
            </button>
            <button
              type="button"
              className={`inspector-tab ${activeInspectTab === 'raw' ? 'active' : ''}`}
              onClick={() => setActiveInspectTab('raw')}
            >
              <Terminal size={14} />
              <span>Raw JSON Artifact</span>
            </button>
          </div>

          {isLoadingInspection ? (
            <div className="inspector-loading">
              <RefreshCw size={20} className="spin-icon text-accent" />
              <span>Loading evaluation artifacts & telemetry...</span>
            </div>
          ) : (
            <div className="inspector-content">
              {activeInspectTab === 'summary' && (
                <div className="inspector-summary-view">
                  {(() => {
                    const baseData =
                      inspectionSummary?.baseline ||
                      (inspectionSummary?.mode === 'baseline' ? inspectionSummary : null);
                    const dynData =
                      inspectionSummary?.dynamic ||
                      (inspectionSummary?.mode === 'dynamic' ? inspectionSummary : null);

                    if (!baseData && !dynData) {
                      return (
                        <div className="inspector-empty">
                          No summary artifact available for this run. Raw event logs may still be viewed under the Lifecycle Events or Raw JSON tabs.
                        </div>
                      );
                    }

                    return (
                      <div className="summary-grid">
                        {baseData && (
                          <div className="summary-mode-card baseline-card">
                            <div className="summary-mode-header">
                              <span className="mode-badge baseline">Baseline Run</span>
                              <span className="font-mono text-xs text-muted">{baseData.experiment_id || baseData.evaluation_id}</span>
                            </div>
                            <div className="summary-metrics-list">
                              <div className="metric-row">
                                <span>Status:</span>
                                <span className="font-semibold">{baseData.status || 'completed'}</span>
                              </div>
                              <div className="metric-row">
                                <span>Context Size:</span>
                                <span className="font-mono font-bold">{(baseData.context_chars ?? baseData.context_size ?? 0).toLocaleString()} chars</span>
                              </div>
                              <div className="metric-row">
                                <span>Actual Input Tokens:</span>
                                <span className="font-mono">
                                  {baseData.token_usage_available && baseData.input_tokens !== null
                                    ? `${baseData.input_tokens.toLocaleString()} tokens`
                                    : 'N/A — token usage unavailable'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>Actual Output Tokens:</span>
                                <span className="font-mono">
                                  {baseData.token_usage_available && baseData.output_tokens !== null
                                    ? `${baseData.output_tokens.toLocaleString()} tokens`
                                    : 'N/A — token usage unavailable'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>Total Tokens:</span>
                                <span className="font-mono">
                                  {baseData.token_usage_available && baseData.total_tokens !== null
                                    ? `${baseData.total_tokens.toLocaleString()} tokens`
                                    : 'N/A — token usage unavailable'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>LLM Calls:</span>
                                <span>{baseData.llm_calls ?? 1} call(s)</span>
                              </div>
                              <div className="metric-row">
                                <span>MCP Calls:</span>
                                <span>{baseData.mcp_calls ?? 0} MCP call(s)</span>
                              </div>
                              <div className="metric-row">
                                <span>Total Experiment Time:</span>
                                <span className="font-mono">{(baseData.total_experiment_time_ms ?? baseData.total_time_ms ?? 0).toFixed(1)} ms</span>
                              </div>
                              <div className="metric-row">
                                <span>Root Cause Identified:</span>
                                <span>{baseData.root_cause_identified ? 'Yes' : 'No'}</span>
                              </div>
                              <div className="metric-row">
                                <span>Re-execution Passed:</span>
                                <span>{baseData.re_execution_passed ? 'Passed (Exit 0)' : 'Failed'}</span>
                              </div>
                              <div className="metric-row">
                                <span>Fix Correct:</span>
                                <span className={
                                  baseData.fix_correct === true
                                    ? 'text-success font-semibold'
                                    : baseData.fix_correct === false
                                    ? 'text-error font-semibold'
                                    : 'text-muted'
                                }>
                                  {baseData.fix_correct === true ? 'Validated' : baseData.fix_correct === false ? 'Failed' : 'Not Validated'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>Stop Reason:</span>
                                <span className="text-xs text-muted">{baseData.stop_reason || 'completed'}</span>
                              </div>
                            </div>
                          </div>
                        )}

                        {dynData && (
                          <div className="summary-mode-card dynamic-card">
                            <div className="summary-mode-header">
                              <span className="mode-badge dynamic">Dynamic Run</span>
                              <span className="font-mono text-xs text-muted">{dynData.experiment_id || dynData.evaluation_id}</span>
                            </div>
                            <div className="summary-metrics-list">
                              <div className="metric-row">
                                <span>Status:</span>
                                <span className="font-semibold">{dynData.status || 'completed'}</span>
                              </div>
                              <div className="metric-row">
                                <span>Context Size:</span>
                                <span className="font-mono font-bold text-success">{(dynData.context_chars ?? dynData.context_size ?? 0).toLocaleString()} chars</span>
                              </div>
                              <div className="metric-row">
                                <span>Actual Input Tokens:</span>
                                <span className="font-mono">
                                  {dynData.token_usage_available && dynData.input_tokens !== null
                                    ? `${dynData.input_tokens.toLocaleString()} tokens (Curator: ${dynData.curator_input_tokens ?? 0}, Debugger: ${dynData.debugger_input_tokens ?? 0})`
                                    : 'N/A — token usage unavailable'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>Actual Output Tokens:</span>
                                <span className="font-mono">
                                  {dynData.token_usage_available && dynData.output_tokens !== null
                                    ? `${dynData.output_tokens.toLocaleString()} tokens (Curator: ${dynData.curator_output_tokens ?? 0}, Debugger: ${dynData.debugger_output_tokens ?? 0})`
                                    : 'N/A — token usage unavailable'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>Total Tokens:</span>
                                <span className="font-mono">
                                  {dynData.token_usage_available && dynData.total_tokens !== null
                                    ? `${dynData.total_tokens.toLocaleString()} tokens (Curator: ${dynData.curator_total_tokens ?? 0}, Debugger: ${dynData.debugger_total_tokens ?? 0})`
                                    : 'N/A — token usage unavailable'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>LLM Calls:</span>
                                <span>{dynData.llm_calls ?? 1} call(s)</span>
                              </div>
                              <div className="metric-row">
                                <span>MCP Calls:</span>
                                <span>{dynData.mcp_calls ?? 0} MCP call(s)</span>
                              </div>
                              <div className="metric-row">
                                <span>Total Experiment Time:</span>
                                <span className="font-mono">{(dynData.total_experiment_time_ms ?? dynData.total_time_ms ?? 0).toFixed(1)} ms</span>
                              </div>
                              <div className="metric-row">
                                <span>Root Cause Identified:</span>
                                <span>{dynData.root_cause_identified ? 'Yes' : 'No'}</span>
                              </div>
                              <div className="metric-row">
                                <span>Re-execution Passed:</span>
                                <span>{dynData.re_execution_passed ? 'Passed (Exit 0)' : 'Failed'}</span>
                              </div>
                              <div className="metric-row">
                                <span>Fix Correct:</span>
                                <span className={
                                  dynData.fix_correct === true
                                    ? 'text-success font-semibold'
                                    : dynData.fix_correct === false
                                    ? 'text-error font-semibold'
                                    : 'text-muted'
                                }>
                                  {dynData.fix_correct === true ? 'Validated' : dynData.fix_correct === false ? 'Failed' : 'Not Validated'}
                                </span>
                              </div>
                              <div className="metric-row">
                                <span>Stop Reason:</span>
                                <span className="text-xs text-muted">{dynData.stop_reason || 'completed'}</span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}

              {activeInspectTab === 'events' && (
                <div className="inspector-events-view">
                  {inspectionEvents && inspectionEvents.length > 0 ? (
                    <div className="events-timeline">
                      {inspectionEvents.map((evt, idx) => (
                        <div key={`${evt.event}-${idx}`} className="event-timeline-node">
                          <div className="event-timeline-left">
                            <span className="event-step-pill">Step {evt.step ?? idx + 1}</span>
                            <span className="event-time-str">
                              {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '-'}
                            </span>
                          </div>
                          <div className="event-timeline-right">
                            <div className="event-title-line">
                              <span className="event-name-tag">{evt.event}</span>
                              {evt.mode && (
                                <span className={`mode-badge ${evt.mode}`}>{evt.mode}</span>
                              )}
                            </div>
                            <div className="event-details-text">
                              {Object.entries(evt)
                                .filter(([k]) => !['timestamp', 'evaluation_id', 'experiment_id', 'event', 'step', 'mode'].includes(k))
                                .map(([k, v]) => (
                                  <span key={k} className="event-kv-item">
                                    <span className="kv-key">{k}:</span>{' '}
                                    <span className="kv-val">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                                  </span>
                                ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="inspector-empty">No structured events recorded for this evaluation ID.</div>
                  )}
                </div>
              )}

              {activeInspectTab === 'raw' && (
                <div className="inspector-raw-view">
                  <pre className="raw-json-block">
                    {JSON.stringify(inspectionSummary || inspectionEvents || inspectedRecord, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 6. Experiment History / Dataset Section */}
      <div className="experiments-history-card">
        <div className="history-card-header">
          <div className="flex-row items-center gap-2">
            <Database size={16} className="text-accent" />
            <h4>Evaluation Experiment History</h4>
          </div>
          <span className="text-muted text-xs">Canonical benchmark dataset</span>
        </div>

        {recentExperiments.length === 0 ? (
          <div className="empty-history">
            <Database size={28} className="empty-icon text-dim" />
            <p className="empty-title">No Evaluation Runs Recorded</p>
            <p className="empty-subtitle">Select a benchmark task above and click <strong>"Run Paired Evaluation"</strong> to record experimental metrics.</p>
          </div>
        ) : (
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Evaluation ID</th>
                  <th>Experiment ID</th>
                  <th>Bug</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Context Size (chars)</th>
                  <th>Context Reduct %</th>
                  <th>Total Tokens</th>
                  <th>MCP Calls</th>
                  <th>Total Time (ms)</th>
                  <th>Fix Correct</th>
                  <th>Timestamp</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentExperiments.map((exp) => (
                  <tr key={exp.experiment_id}>
                    <td className="font-mono text-xs" title={exp.evaluation_id}>
                      {exp.evaluation_id ? exp.evaluation_id.slice(0, 16) + '...' : '-'}
                    </td>
                    <td className="font-mono text-xs" title={exp.experiment_id}>
                      {exp.experiment_id ? exp.experiment_id.slice(-14) : '-'}
                    </td>
                    <td className="font-bold">{exp.bug_id}</td>
                    <td>
                      <span className={`mode-badge ${exp.mode}`}>
                        {exp.mode === 'baseline' ? 'Baseline' : 'Dynamic'}
                      </span>
                    </td>
                    <td>
                      <span className={`status-tag ${exp.status === 'completed' ? 'completed' : 'invalid'}`}>
                        {exp.status === 'completed' ? 'Completed' : exp.status}
                      </span>
                    </td>
                    <td>{(exp.context_chars ?? exp.context_size ?? 0).toLocaleString()} chars</td>
                    <td>{formatTableReduction(exp.context_reduction_percent)}</td>
                    <td>
                      {exp.token_usage_available && exp.total_tokens !== null
                        ? exp.total_tokens.toLocaleString()
                        : 'N/A'}
                    </td>
                    <td>{exp.mcp_calls}</td>
                    <td>{(exp.total_experiment_time_ms || exp.total_time_ms || 0).toFixed(0)} ms</td>
                    <td>
                      {exp.fix_correct === true ? (
                        <span className="text-success text-xs font-semibold">Validated</span>
                      ) : exp.fix_correct === false ? (
                        <span className="text-error text-xs font-semibold">Failed</span>
                      ) : (
                        <span className="text-muted text-xs">Not Validated</span>
                      )}
                    </td>
                    <td className="text-xs text-muted">
                      {exp.timestamp ? new Date(exp.timestamp).toLocaleTimeString() : '-'}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="table-inspect-btn"
                        onClick={() => handleInspectEvaluation(exp.evaluation_id, exp)}
                        title="Inspect run artifacts and telemetry"
                      >
                        <Eye size={12} />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 7. Clear Results Confirmation Modal Dialog */}
      {isClearModalOpen && (
        <div className="modal-overlay" onClick={handleCloseClearModal}>
          <div
            className="clear-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="clear-dialog-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="flex-row items-center gap-2">
                <AlertTriangle size={18} className="text-error" />
                <h4 id="clear-dialog-title">Clear M8 Experiment Results?</h4>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={handleCloseClearModal}
                disabled={isClearing}
                title="Cancel and close dialog"
              >
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              <p className="modal-lead-text">
                Clear all saved M8 experiment results and generated artifacts? Benchmark definitions and source code will be preserved. This action cannot be undone.
              </p>

              <div className="modal-scope-box">
                <div className="scope-col scope-col-delete">
                  <span className="scope-col-title text-error">Permanently Removed:</span>
                  <ul className="scope-list">
                    <li>Master dataset rows (<code>m8_experiments.csv</code> will be reset to header)</li>
                    <li>Lifecycle telemetry journal (<code>m8_events.jsonl</code> will be cleared)</li>
                    <li>All per-experiment artifact directories (<code>summary.json</code>, <code>baseline.json</code>, <code>dynamic.json</code>, etc.)</li>
                  </ul>
                </div>
                <div className="scope-col scope-col-preserve">
                  <span className="scope-col-title text-success">Preserved:</span>
                  <ul className="scope-list">
                    <li>Benchmark task definitions (B001–B010)</li>
                    <li>Application settings, configurations, and source code</li>
                    <li>General server application logs</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                id="cancel-clear-btn"
                className="action-btn secondary-btn"
                onClick={handleCloseClearModal}
                disabled={isClearing}
              >
                Cancel
              </button>
              <button
                type="button"
                id="confirm-clear-btn"
                className="action-btn danger-btn confirm-clear-btn"
                onClick={handleConfirmClear}
                disabled={isClearing || isRunning}
              >
                {isClearing ? (
                  <>
                    <RefreshCw size={14} className="spin-icon" />
                    <span>Clearing Results...</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    <span>Confirm Clear</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
