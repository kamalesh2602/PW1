import React from 'react';
import { Terminal, Shield } from 'lucide-react';

export const Header = () => {
  return (
    <header className="app-header">
      <div className="header-content">
        <div className="title-group">
          <div className="icon-wrapper">
            <Terminal className="header-icon" size={24} />
          </div>
          <div>
            <h1 className="header-title">PW1</h1>
            <p className="header-subtitle">Secure code execution for Python and Java</p>
          </div>
        </div>
        
      </div>
    </header>
  );
};
