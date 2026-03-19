import { useState } from 'react';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { apiService } from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!apiService.getToken());

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    apiService.setToken(null);
    setIsAuthenticated(false);
  };

  return isAuthenticated ? (
    <Dashboard onLogout={handleLogout} />
  ) : (
    <Login onLogin={handleLogin} />
  );
}

export default App;
