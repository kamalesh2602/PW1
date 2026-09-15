import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 45000,
});

export async function diagnoseExecution(executionId) {
  if (!executionId) {
    throw new Error('Execution ID is required for diagnosis.');
  }

  try {
    const response = await apiClient.post('/debug/diagnose', {
      execution_id: executionId,
    });
    return response.data;
  } catch (error) {
    if (error.response && error.response.status === 500) {
      throw new Error('Unable to generate fix. Please try again.');
    } else if (error.code === 'ECONNABORTED') {
      throw new Error('Unable to generate fix. Please try again.');
    } else if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    } else {
      throw new Error('Unable to generate fix. Please try again.');
    }
  }
}

export async function fixExecution(executionId, maxAttempts = 3) {
  if (!executionId) {
    throw new Error('Execution ID is required for automatic fixing.');
  }

  try {
    const response = await apiClient.post('/debug/fix', {
      execution_id: executionId,
      max_attempts: maxAttempts,
    });
    return response.data;
  } catch (error) {
    if (error.response && error.response.status === 500) {
      throw new Error('Unable to generate fix. Please try again.');
    } else if (error.code === 'ECONNABORTED') {
      throw new Error('Unable to generate fix. Please try again.');
    } else if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    } else {
      throw new Error('Unable to generate fix. Please try again.');
    }
  }
}
