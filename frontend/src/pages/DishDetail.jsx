import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useCart } from "../App";
import { getDish, resolveImageUrl } from "../api";

export default function DishDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();
  const [dish, setDish] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDish(id).then(setDish).catch(() => setError("没有找到这道菜。"));
  }, [id]);

  if (error) return <div className="content state-box error">{error}</div>;
  if (!dish) return <div className="content state-box">正在端上来…</div>;

  const addAndGo = () => {
    addItem(dish);
    navigate("/cart");
  };

  return (
    <section className="detail-page">
      <Link to="/" className="back-link">← 返回菜单</Link>
      {dish.image_url ? (
        <img className="detail-image" src={resolveImageUrl(dish.image_url)} alt={dish.name} />
      ) : (
        <div className="detail-image image-placeholder">🍳</div>
      )}
      <div className="detail-card">
        <span className="category-pill static">{dish.category}</span>
        <h1>{dish.name}</h1>
        <p>{dish.description}</p>
        <div className="detail-action">
          <strong>¥{dish.price.toFixed(2)}</strong>
          <button className="primary-button" type="button" onClick={addAndGo}>
            加入点菜清单
          </button>
        </div>
      </div>
    </section>
  );
}
