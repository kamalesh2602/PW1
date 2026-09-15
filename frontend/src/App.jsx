import React, { useState } from 'react';
import { Header } from './components/Header';
import { LanguageSelector } from './components/LanguageSelector';
import { FileUploadButton } from './components/FileUploadButton';
import { RunButton } from './components/RunButton';
import { CodeEditor } from './components/CodeEditor';
import { InputPanel } from './components/InputPanel';
import { OutputPanel } from './components/OutputPanel';
import { FixHistorySection } from './components/FixHistorySection';
import { executeCode } from './services/api';
import { diagnoseExecution, fixExecution } from './services/fixService';

const STARTER_CODE = {
  python: `def main():
    # Buggy code example: division by zero
    numbers = [10, 20, 0, 40]
    total = 100
    for num in numbers:
        result = total / num
        print(f"Result: {result}")

main()`,
  java: `public class Main {
    public static void main(String[] args) {
        // Buggy code example: array out of bounds
        int[] arr = {1, 2, 3};
        for (int i = 0; i <= arr.length; i++) {
            System.out.println("Element: " + arr[i]);
        }
    }
}`,
};

export default function App() {
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState(STARTER_CODE.python);
  const [stdin, setStdin] = useState('');
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Module 6 & Debugging States
  const [diagnosis, setDiagnosis] = useState(null);
  const [fixResult, setFixResult] = useState(null);
  const [isFixing, setIsFixing] = useState(false);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [fixStep, setFixStep] = useState('');
  const [fixError, setFixError] = useState(null);
  const [fixHistory, setFixHistory] = useState([]);

  const handleLanguageChange = (newLanguage) => {
    setLanguage(newLanguage);
    setCode(STARTER_CODE[newLanguage] || '');
    setUploadedFileName(null);
    setResult(null);
    setDiagnosis(null);
    setFixResult(null);
    setFixError(null);
  };

  const handleFileUpload = (fileName, fileContent, detectedLanguage) => {
    if (detectedLanguage) {
      setLanguage(detectedLanguage);
    }
    setCode(fileContent);
    setUploadedFileName(fileName);
    setResult(null);
    setDiagnosis(null);
    setFixResult(null);
    setFixError(null);
  };

  const handleResetCode = () => {
    setUploadedFileName(null);
    setCode(STARTER_CODE[language] || '');
    setResult(null);
    setDiagnosis(null);
    setFixResult(null);
    setFixError(null);
  };

  const handleRunCode = async () => {
    setIsLoading(true);
    setDiagnosis(null);
    setFixResult(null);
    setFixError(null);

    try {
      const response = await executeCode(language, code, stdin);
      setResult(response);
    } catch (err) {
      setResult({
        status: 'execution_error',
        language,
        stdout: '',
        stderr: err.message || 'An unknown error occurred during execution.',
        exit_code: 1,
        execution_time: 0,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDiagnose = async () => {
    if (!result || !result.execution_id) {
      setFixError('No valid execution ID found to run diagnosis.');
      return;
    }

    setIsDiagnosing(true);
    setFixError(null);

    try {
      const diagData = await diagnoseExecution(result.execution_id);
      setDiagnosis(diagData);
    } catch (err) {
      setFixError(err.message || 'Unable to generate diagnosis. Please try again.');
    } finally {
      setIsDiagnosing(false);
    }
  };

  const handleFixWithAI = async () => {
    if (!result || !result.execution_id) {
      setFixError('No valid execution ID found for automatic fixing.');
      return;
    }

    setIsFixing(true);
    setFixError(null);
    setFixResult(null);

    // Step 1: Generating diagnosis...
    setFixStep('Generating diagnosis...');

    // Simulate visible progress transition for UX
    const stepTimer1 = setTimeout(() => {
      setFixStep('Generating patch...');
    }, 1200);

    const stepTimer2 = setTimeout(() => {
      setFixStep('Validating fix...');
    }, 2600);

    try {
      const res = await fixExecution(result.execution_id, 3);
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);

      setFixResult(res);
      if (res.original_diagnosis) {
        setDiagnosis(res.original_diagnosis);
      }

      // Add to Fix History
      const newHistoryItem = {
        executionId: result.execution_id,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        success: res.success,
        attempts: res.attempts,
        fixedCode: res.fixed_code,
        diagnosis: res.original_diagnosis,
      };
      setFixHistory((prev) => [newHistoryItem, ...prev]);
    } catch (err) {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      setFixError('Unable to generate fix. Please try again.');
    } finally {
      setIsFixing(false);
      setFixStep('');
    }
  };

  const handleApplyFix = (fixedCode) => {
    if (!fixedCode) return;
    setCode(fixedCode);
  };

  const handleSelectHistoryItem = (item) => {
    if (item.fixedCode) {
      setFixResult({
        execution_id: item.executionId,
        success: item.success,
        attempts: item.attempts,
        fixed_code: item.fixedCode,
        final_execution_id: item.executionId,
        final_error: null,
        original_diagnosis: item.diagnosis,
      });
    }
    if (item.diagnosis) {
      setDiagnosis(item.diagnosis);
    }
  };

  const handleClearHistory = () => {
    setFixHistory([]);
  };

  return (
    <div className="app-container">
      <Header />
      <main className="main-content">
        <div className="toolbar flex-row">
          <div className="toolbar-left">
            <LanguageSelector
              language={language}
              onLanguageChange={handleLanguageChange}
              disabled={isLoading || isFixing}
            />
            <FileUploadButton
              onFileUpload={handleFileUpload}
              disabled={isLoading || isFixing}
            />
          </div>
          <RunButton onRun={handleRunCode} isLoading={isLoading || isFixing} />
        </div>

        <div className="workspace-grid">
          <div className="grid-cell editor-cell">
            <CodeEditor
              language={language}
              code={code}
              onChange={setCode}
              uploadedFileName={uploadedFileName}
              onResetCode={handleResetCode}
              onFileUpload={handleFileUpload}
            />
          </div>
          <div className="right-panel-column">
            <div className="grid-cell input-cell">
              <InputPanel
                stdin={stdin}
                onChange={setStdin}
                disabled={isLoading || isFixing}
              />
            </div>
            <div className="grid-cell output-cell">
              <OutputPanel
                result={result}
                isLoading={isLoading}
                isDiagnosing={isDiagnosing}
                isFixing={isFixing}
                fixStep={fixStep}
                diagnosis={diagnosis}
                fixResult={fixResult}
                fixError={fixError}
                onDiagnose={handleDiagnose}
                onFixWithAI={handleFixWithAI}
                onApplyFix={handleApplyFix}
                originalCode={code}
                language={language}
              />
            </div>
            {fixHistory.length > 0 && (
              <div className="grid-cell history-cell">
                <FixHistorySection
                  history={fixHistory}
                  onSelectHistoryItem={handleSelectHistoryItem}
                  onClearHistory={handleClearHistory}
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
