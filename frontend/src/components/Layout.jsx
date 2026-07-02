import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useCart } from "../App";

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { count } = useCart();
  const isAdmin = location.pathname.startsWith("/admin");
  const isAdminLogin = location.pathname === "/admin/login";

  const logout = () => {
    localStorage.removeItem("admin_token");
    navigate("/admin/login", { replace: true });
  };

  return (
    <div className="app-shell">
      <header className={`topbar ${isAdmin ? "admin-topbar" : ""}`}>
        <Link to={isAdmin ? "/admin" : "/"} className="brand">
          <span className="brand-mark">♡</span>
          <span>{isAdmin ? "小厨房管理台" : "宝贝专属菜单"}</span>
        </Link>
        {isAdmin && !isAdminLogin ? (
          <nav className="admin-nav" aria-label="管理端导航">
            <Link className={location.pathname === "/admin" ? "active" : ""} to="/admin">订单</Link>
            <Link className={location.pathname === "/admin/dishes" ? "active" : ""} to="/admin/dishes">菜品</Link>
            <Link className={location.pathname === "/admin/stats" ? "active" : ""} to="/admin/stats">点菜统计</Link>
            <button type="button" onClick={logout}>退出登录</button>
          </nav>
        ) : isAdminLogin ? (
          <Link className="small-link" to="/">返回点菜</Link>
        ) : (
          <Link className="cart-link" to="/cart" aria-label="点菜清单">
            🛒
            {count > 0 && <span className="cart-badge">{count}</span>}
          </Link>
        )}
      </header>
      <main>
        <Outlet />
      </main>
      {!isAdmin && (
        <footer className="footer">
          每一顿饭，都想认真做给你吃 <span>♥</span>
        </footer>
      )}
    </div>
  );
}
