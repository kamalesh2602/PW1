import React, { useState } from 'react';
import { Header } from './components/Header';
import { LanguageSelector } from './components/LanguageSelector';
import { FileUploadButton } from './components/FileUploadButton';
import { RunButton } from './components/RunButton';
import { CodeEditor } from './components/CodeEditor';
import { OutputPanel } from './components/OutputPanel';
import { executeCode } from './services/api';

const STARTER_CODE = {
  python: `def main():
    print("Hello from Python")

main()`,
  java: `public class Main {
    public static void main(String[] args) {
        System.out.println("Hello from Java");
    }
}`,
};

export default function App() {
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState(STARTER_CODE.python);
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleLanguageChange = (newLanguage) => {
    setLanguage(newLanguage);
    setCode(STARTER_CODE[newLanguage] || '');
    setUploadedFileName(null);
    setResult(null);
  };

  const handleFileUpload = (fileName, fileContent, detectedLanguage) => {
    if (detectedLanguage) {
      setLanguage(detectedLanguage);
    }
    setCode(fileContent);
    setUploadedFileName(fileName);
    setResult(null);
  };

  const handleResetCode = () => {
    setUploadedFileName(null);
    setCode(STARTER_CODE[language] || '');
    setResult(null);
  };

  const handleRunCode = async () => {
    setIsLoading(true);
    try {
      const response = await executeCode(language, code);
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

  return (
    <div className="app-container">
      <Header />
      <main className="main-content">
        <div className="toolbar flex-row">
          <div className="toolbar-left">
            <LanguageSelector
              language={language}
              onLanguageChange={handleLanguageChange}
              disabled={isLoading}
            />
            <FileUploadButton
              onFileUpload={handleFileUpload}
              disabled={isLoading}
            />
          </div>
          <RunButton onRun={handleRunCode} isLoading={isLoading} />
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
          <div className="grid-cell output-cell">
            <OutputPanel result={result} isLoading={isLoading} />
          </div>
        </div>
      </main>
    </div>
  );
}
