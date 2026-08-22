import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000, // 15 seconds network timeout
});

export const executeCode = async (language, code, stdin = '') => {
  try {
    const response = await apiClient.post('/execute', {
      language,
      code,
      stdin,
    });
    return response.data;
  } catch (error) {
    if (error.response && error.response.data) {
      return {
        status: 'execution_error',
        language,
        stdout: '',
        stderr: error.response.data.detail || 'Backend API error occurred.',
        exit_code: 1,
        execution_time: 0,
      };
    } else if (error.code === 'ECONNABORTED') {
      return {
        status: 'timeout',
        language,
        stdout: '',
        stderr: 'Network request timed out contacting execution backend.',
        exit_code: null,
        execution_time: 15.0,
      };
    } else {
      return {
        status: 'execution_error',
        language,
        stdout: '',
        stderr: `Unable to connect to backend execution service (${API_URL}). Please ensure the FastAPI backend is running.`,
        exit_code: 1,
        execution_time: 0,
      };
    }
  }
};
