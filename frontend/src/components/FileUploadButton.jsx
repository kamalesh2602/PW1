import React, { useRef } from 'react';
import { Upload } from 'lucide-react';

export const FileUploadButton = ({ onFileUpload, disabled }) => {
  const fileInputRef = useRef(null);

  const handleButtonClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Determine language based on extension
    const ext = file.name.split('.').pop()?.toLowerCase();
    let detectedLanguage = null;
    if (ext === 'py') {
      detectedLanguage = 'python';
    } else if (ext === 'java') {
      detectedLanguage = 'java';
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result;
      if (typeof content === 'string') {
        onFileUpload(file.name, content, detectedLanguage);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="file-upload-wrapper">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".py,.java,.txt,.c,.cpp,.js"
        style={{ display: 'none' }}
      />
      <button
        type="button"
        onClick={handleButtonClick}
        disabled={disabled}
        className="upload-button"
        title="Upload code file (.py, .java, .txt)"
      >
        <Upload size={16} />
        <span>Upload File</span>
      </button>
    </div>
  );
};
