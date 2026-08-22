import React, { useEffect, useRef, useState } from 'react';
import { Terminal as Xterm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { Terminal as TerminalIcon, Play, Square, Trash2, Wifi } from 'lucide-react';

export const InteractiveTerminal = ({ language, code, onExecutionFinish }) => {
  const terminalRef = useRef(null);
  const xtermRef = useRef(null);
  const fitAddonRef = useRef(null);
  const socketRef = useRef(null);

  const [isRunning, setIsRunning] = useState(false);
  const [statusText, setStatusText] = useState('Idle');

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize Xterm.js instance
    const term = new Xterm({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "'JetBrains Mono', Consolas, 'Courier New', monospace",
      theme: {
        background: '#0e0d17',
        foreground: '#f8fafc',
        cursor: '#C06C84',
        selectionBackground: 'rgba(192, 108, 132, 0.3)',
        black: '#141322',
        red: '#ef4444',
        green: '#10b981',
        yellow: '#f59e0b',
        blue: '#355C7D',
        magenta: '#C06C84',
        cyan: '#6C5B7B',
        white: '#f8fafc',
      },
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    term.writeln('\x1b[90mInteractive Terminal Ready. Click "Run Code Live" to execute program with real-time prompt interaction.\x1b[0m');

    // Send typed characters over WebSocket to program stdin
    term.onData((data) => {
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'input', data }));
      }
    });

    const handleResize = () => {
      if (fitAddonRef.current) {
        try {
          fitAddonRef.current.fit();
        } catch (e) {
          // ignore resize errors
        }
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (socketRef.current) {
        socketRef.current.close();
      }
      term.dispose();
    };
  }, []);

  const runLiveCode = () => {
    if (isRunning) return;

    const term = xtermRef.current;
    if (!term) return;

    term.clear();
    term.writeln(`\x1b[36m[Launching live ${language} program...]\x1b[0m\r\n`);
    setIsRunning(true);
    setStatusText('Running');

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname || 'localhost';
    const wsPort = '8000';
    const wsUrl = `${wsProtocol}//${wsHost}:${wsPort}/ws/execute`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      // Send initial execution request payload
      socket.send(JSON.stringify({ language, code }));
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'stdout') {
          term.write(msg.data);
        } else if (msg.type === 'stderr') {
          term.write(`\x1b[31m${msg.data}\x1b[0m`);
        } else if (msg.type === 'exit') {
          const color = msg.exit_code === 0 ? '\x1b[32m' : '\x1b[31m';
          term.writeln(`\r\n${color}[Process exited with code ${msg.exit_code} in ${msg.execution_time}s]\x1b[0m`);
          setIsRunning(false);
          setStatusText('Finished');
          if (onExecutionFinish) {
            onExecutionFinish(msg);
          }
        }
      } catch (e) {
        term.write(event.data);
      }
    };

    socket.onerror = () => {
      term.writeln('\r\n\x1b[31m[WebSocket connection error. Is backend server running on port 8000?]\x1b[0m');
      setIsRunning(false);
      setStatusText('Error');
    };

    socket.onclose = () => {
      setIsRunning(false);
    };
  };

  const stopExecution = () => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setIsRunning(false);
    setStatusText('Stopped');
    if (xtermRef.current) {
      xtermRef.current.writeln('\r\n\x1b[33m[Execution terminated by user]\x1b[0m');
    }
  };

  const clearTerminal = () => {
    if (xtermRef.current) {
      xtermRef.current.clear();
    }
  };

  return (
    <div className="interactive-terminal-container">
      <div className="terminal-header">
        <div className="terminal-title">
          <TerminalIcon size={16} />
          <span>Interactive Live Terminal</span>
          <span className={`connection-badge ${isRunning ? 'running' : 'idle'}`}>
            <Wifi size={12} />
            <span>{statusText}</span>
          </span>
        </div>
        <div className="terminal-controls">
          {!isRunning ? (
            <button
              type="button"
              onClick={runLiveCode}
              className="run-live-btn"
              title="Run code interactively with real-time keyboard input"
            >
              <Play size={14} fill="currentColor" />
              <span>Run Live</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={stopExecution}
              className="stop-live-btn"
              title="Terminate running process"
            >
              <Square size={14} fill="currentColor" />
              <span>Stop</span>
            </button>
          )}
          <button
            type="button"
            onClick={clearTerminal}
            className="clear-terminal-btn"
            title="Clear terminal screen"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      <div className="terminal-viewport" ref={terminalRef} />
    </div>
  );
};
