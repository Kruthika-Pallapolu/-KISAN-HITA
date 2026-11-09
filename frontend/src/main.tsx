import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

type StartupDiagnostics = {
  mark: (phase: string) => void;
  report: (error: Error, info: React.ErrorInfo) => void;
  mounted: () => void;
};

const diagnostics = (window as Window & { __KH_STARTUP_DIAGNOSTICS__?: StartupDiagnostics })
  .__KH_STARTUP_DIAGNOSTICS__;
diagnostics?.mark('entry module evaluated; static imports completed');

class StartupErrorBoundary extends React.Component<React.PropsWithChildren, { failed: boolean }> {
  state = { failed: false };

  componentDidMount() {
    diagnostics?.mounted();
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.setState({ failed: true });
    diagnostics?.report(error, info);
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

diagnostics?.mark('creating React root');
const rootElement = document.getElementById('root');
if (!rootElement) {
  const error = new Error('Required #root element was not found in index.html');
  diagnostics?.report(error, { componentStack: '' });
  throw error;
}

const root = ReactDOM.createRoot(rootElement);
diagnostics?.mark('React root created; initial render requested');
root.render(
  <React.StrictMode>
    {diagnostics ? <StartupErrorBoundary><App /></StartupErrorBoundary> : <App />}
  </React.StrictMode>
);

