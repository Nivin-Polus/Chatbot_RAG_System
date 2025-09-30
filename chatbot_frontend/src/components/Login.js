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
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="mx-auto h-16 w-16 bg-primary-600 rounded-full flex items-center justify-center mb-6">
            <span className="text-white text-2xl">🤖</span>
          </div>
          <h2 className="text-3xl font-bold text-gray-900">Welcome Back</h2>
          <p className="mt-2 text-sm text-gray-600">Sign in to your knowledge base account</p>
        </div>
        
        <div className="bg-white py-8 px-6 shadow-soft rounded-xl border border-gray-200">
          <form className="space-y-6" onSubmit={handleLogin}>
            <div className="form-group">
              <label htmlFor="username" className="form-label">
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                className="form-input"
                placeholder="Enter your username"
                value={username}
                onChange={e => setUsername(e.target.value)}
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="password" className="form-label">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className="form-input"
                placeholder="Enter your password"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <div className="alert alert-error">
                <span className="alert-icon">❌</span>
                <span className="alert-message">{error}</span>
              </div>
            )}

            <div>
              <button
                type="submit"
                className="w-full btn btn-primary btn-lg"
              >
                <span className="mr-2">🔐</span>
                Sign In
              </button>
            </div>
          </form>
        </div>
        
        <div className="text-center">
          <p className="text-xs text-gray-500">
            Secure access to your knowledge base system
          </p>
        </div>
      </div>
    </div>
  );
}
