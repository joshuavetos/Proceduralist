import React, { useState } from 'react';
import Landing from './Landing';
import Dashboard from './Dashboard';

function App() {
  const [view, setView] = useState('landing');

  return view === 'landing' ? (
    <Landing onEnter={() => setView('dashboard')} />
  ) : (
    <Dashboard onBack={() => setView('landing')} />
  );
}

export default App;
