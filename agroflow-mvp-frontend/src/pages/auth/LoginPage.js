import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getApiError } from "../../utils/errors";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate("/");
    } catch (err) {
      setError(getApiError(err, "Login failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-vh-100 d-flex align-items-center justify-content-center bg-light p-3">
      <form onSubmit={submit} className="card shadow-sm border-0 p-4" style={{ width: 420 }}>
        <h2 className="fw-bold">AgroFlow</h2>
        <p className="text-muted">Procurement decision-support and traceability.</p>
        {error && <div className="alert alert-danger">{error}</div>}
        <label className="form-label">Email</label>
        <input className="form-control mb-3" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label className="form-label">Password</label>
        <input className="form-control mb-3" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button className="btn btn-dark w-100" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <div className="text-center mt-3 small">
          New organization? <Link to="/register">Register</Link>
        </div>
      </form>
    </div>
  );
}
