import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 3 minutes timeout for multi-step agent and Docker re-execution
});

export async function getBenchmarks(language = 'python') {
  const langParam = language ? `?language=${encodeURIComponent(language)}` : '';
  const response = await apiClient.get(`/evaluation/benchmarks${langParam}`);
  return response.data;
}

export async function getBenchmarkById(bugId, language = 'python') {
  const langParam = language ? `?language=${encodeURIComponent(language)}` : '';
  const response = await apiClient.get(`/evaluation/benchmarks/${encodeURIComponent(bugId)}${langParam}`);
  return response.data;
}

export async function runSingleEvaluation({ bugId, mode, code, language, stdin }) {
  const response = await apiClient.post('/evaluation/run', {
    bug_id: bugId,
    mode,
    code,
    language,
    stdin,
  });
  return response.data;
}

export async function runPairedEvaluation({ bugId, code, language, stdin }) {
  const response = await apiClient.post('/evaluation/run-paired', {
    bug_id: bugId,
    code,
    language,
    stdin,
  });
  return response.data;
}

export async function getRecentExperiments(limit = 20) {
  const response = await apiClient.get(`/evaluation/experiments?limit=${limit}`);
  return response.data;
}

export function getExportCsvUrl() {
  return `${API_URL}/evaluation/export/csv`;
}

export async function getExperimentSummary(evaluationId) {
  const response = await apiClient.get(`/evaluation/experiments/${evaluationId}/summary`);
  return response.data;
}

export async function getExperimentEvents(evaluationId) {
  const response = await apiClient.get(`/evaluation/experiments/${evaluationId}/events`);
  return response.data;
}

export async function clearEvaluationResults() {
  const response = await apiClient.delete('/evaluation/results');
  return response.data;
}

