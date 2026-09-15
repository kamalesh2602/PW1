import React from 'react';
import ReactDOM from 'react-dom/client';
import { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import App from './App.jsx';
import './index.css';

// Configure Monaco Editor to use local node_modules bundle instead of CDN
loader.config({ monaco });

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
