import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getDishes } from "../api";
import CategoryTabs from "../components/CategoryTabs";
import DishCard from "../components/DishCard";

export default function Home() {
  const [dishes, setDishes] = useState([]);
  const [category, setCategory] = useState("全部");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDishes()
      .then(setDishes)
      .catch(() => setError("菜单暂时走丢了，请确认后端已经启动。"))
      .finally(() => setLoading(false));
  }, []);

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
        <CategoryTabs categories={categories} active={category} onChange={setCategory} />
        {loading && <div className="state-box">正在翻开菜单…</div>}
        {error && <div className="state-box error">{error}</div>}
        {!loading && !error && (
          <div className="dish-grid">
            {visible.map((dish) => <DishCard key={dish.id} dish={dish} />)}
          </div>
        )}
      </section>
    </>
  );
}
