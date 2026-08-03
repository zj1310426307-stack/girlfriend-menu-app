import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="empty-page">
      <div className="empty-icon">🍽️</div>
      <h1>这个页面没有找到</h1>
      <p>可能是链接已经失效，回菜单重新看看吧。</p>
      <Link className="primary-button" to="/">返回菜单</Link>
    </section>
  );
}
