import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { adminLogin } from "../api";

export default function AdminLogin() {
  const navigate = useNavigate();
  const location = useLocation();
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (localStorage.getItem("admin_token")) {
    return <Navigate to="/admin" replace />;
  }

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const result = await adminLogin(password);
      localStorage.setItem("admin_token", result.token);
      navigate(location.state?.from || "/admin", { replace: true });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "登录失败，请稍后再试。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="admin-login-page">
      <form className="admin-login-card" onSubmit={submit}>
        <div className="login-heart">♥</div>
        <span className="eyebrow">PRIVATE KITCHEN</span>
        <h1>进入小厨房</h1>
        <p>输入管理密码后，就可以处理订单和整理菜单啦。</p>
        <label>
          管理密码
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="请输入管理密码"
            required
            autoFocus
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" type="submit" disabled={submitting}>
          {submitting ? "正在登录…" : "登录管理端"}
        </button>
      </form>
    </section>
  );
}
