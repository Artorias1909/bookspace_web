import React, { useState } from "react";

const RegisterForm = ({ onSubmit, onSwitch }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      await onSubmit({ username, password });
    } catch (err) {
      setError(err.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-panel">
      <h2>Create account</h2>
      <p className="auth-sub">Start building your library</p>
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required minLength={3} />
        </div>
        <div className="field">
          <label>Password <span style={{ color: "var(--text-3)", fontWeight: 400 }}>(min. 8 chars)</span></label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </div>
        <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center" }}>
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>
      <div className="auth-switch">
        Already have an account? <button className="link-btn" onClick={onSwitch}>Sign in</button>
      </div>
    </div>
  );
};

export default RegisterForm;
