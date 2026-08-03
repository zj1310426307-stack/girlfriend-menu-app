import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getDishes } from "../api";
import CategoryTabs from "../components/CategoryTabs";
import DishCard from "../components/DishCard";

export default function Home() {
  const [dishes, setDishes] = useState([]);
  const [category, setCategory] = useState("全部");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDishes = useCallback(() => {
    setLoading(true);
    setError("");
    getDishes()
      .then(setDishes)
      .catch(() => setError("菜单暂时走丢了，服务器可能正在醒来。"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(loadDishes, [loadDishes]);

  const categories = useMemo(() => [...new Set(dishes.map((dish) => dish.category))], [dishes]);
  const visible =
    category === "全部" ? dishes : dishes.filter((dish) => dish.category === category);

  return (
    <>
      <section className="hero">
        <span className="eyebrow">TODAY'S MENU</span>
        <h1>今天想吃什么呀？</h1>
        <p>你负责点菜，我负责把喜欢放进每一道菜里。</p>
        <Link className="my-orders-entry" to="/my-orders">♡ 我的点菜单</Link>
      </section>
      <section className="content">
        <Link className="home-game-entry" to="/games/dice">
          <span className="home-game-icon" aria-hidden="true">⚄</span>
          <span>
            <small>BAR GAME · 3D PHYSICS</small>
            <strong>喝酒小游戏</strong>
            <em>来一局大话骰，看看今晚谁先被开</em>
          </span>
          <b aria-hidden="true">进入游戏 →</b>
        </Link>
        <CategoryTabs categories={categories} active={category} onChange={setCategory} />
        {loading && <div className="state-box" aria-live="polite">正在翻开菜单…</div>}
        {error && (
          <div className="state-box error" role="alert">
            <p>{error}</p>
            <button className="retry-button" type="button" onClick={loadDishes}>重新加载菜单</button>
          </div>
        )}
        {!loading && !error && (
          <div className="dish-grid">
            {visible.map((dish) => <DishCard key={dish.id} dish={dish} />)}
          </div>
        )}
        {!loading && !error && visible.length === 0 && (
          <div className="state-box">这个分类还没有菜，换一个看看吧。</div>
        )}
      </section>
    </>
  );
}
