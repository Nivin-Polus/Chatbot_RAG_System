import { useState } from "react";
import api from "../api/api";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      
      const res = await api.post("/auth/token", formData, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });
      
      // Store multi-tenant user data
      localStorage.setItem("access_token", res.data.access_token);
      localStorage.setItem("user_role", res.data.role);
      localStorage.setItem("username", res.data.username);
      localStorage.setItem("website_id", res.data.website_id || "");
      localStorage.setItem("user_id", res.data.user_id || "");
      
      onLogin(res.data);
    } catch (err) {
      console.error("Login error:", err);
      setError(err.response?.data?.detail || "Invalid credentials");
    }
  };

  return (
    <div className="login-container">
      <h2>Login</h2>
      <form onSubmit={handleLogin}>
        <input placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required />
        <input placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        <button type="submit">Login</button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
