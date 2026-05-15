import React, { useEffect, useState } from "react";
import { getToken, saveToken, clearToken } from "./auth";
import { setAuthToken, loginUser, registerUser, fetchMe } from "./api";
import LoginForm from "./components/LoginForm";
import LibraryDashboard from "./components/LibraryDashboard";
import Logo from "./components/Logo";

const App = () => {
  const [user,    setUser]    = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (token) {
      setAuthToken(token);
      fetchMe()
        .then((res) => setUser(res.data))
        .catch(() => { clearToken(); setAuthToken(null); })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  // Returns user data WITHOUT calling setUser — LoginForm delays navigation
  const handleLogin = async (credentials) => {
    const formData = new URLSearchParams();
    formData.append("username", credentials.username);
    formData.append("password", credentials.password);
    const response = await loginUser(formData);
    saveToken(response.data.access_token);
    setAuthToken(response.data.access_token);
    const userResponse = await fetchMe();
    return userResponse.data;
  };

  const handleRegister = async (credentials) => {
    await registerUser(credentials);
    // LoginForm handles the UI transition back to login
  };

  const handleLogout = () => {
    clearToken();
    setAuthToken(null);
    setUser(null);
  };

  if (loading) return null;

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="app-header-brand" href="/">
          <Logo size={32} />
          <span>Book<em>space</em></span>
        </a>
        <div className="app-header-spacer" />
        {user && (
          <div className="app-header-user">
            <strong>{user.username}</strong>
            <button className="btn btn-ghost" onClick={handleLogout}>Sign out</button>
          </div>
        )}
      </header>

      {!user ? (
        <div className="auth-wrap">
          <LoginForm
            onLogin={handleLogin}
            onLoginComplete={setUser}
            onRegister={handleRegister}
          />
        </div>
      ) : (
        <LibraryDashboard user={user} />
      )}
    </div>
  );
};

export default App;
