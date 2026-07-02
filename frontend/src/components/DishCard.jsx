import { Link } from "react-router-dom";

import { useCart } from "../App";
import { resolveImageUrl } from "../api";

export default function DishCard({ dish }) {
  const { addItem } = useCart();

  return (
    <article className="dish-card">
      <Link to={`/dishes/${dish.id}`} className="dish-image-wrap">
        {dish.image_url ? (
          <img className="dish-image" src={resolveImageUrl(dish.image_url)} alt={dish.name} loading="lazy" />
        ) : (
          <div className="image-placeholder">🍳</div>
        )}
        <span className="category-pill">{dish.category}</span>
      </Link>
      <div className="dish-card-body">
        <Link to={`/dishes/${dish.id}`} className="dish-title">
          {dish.name}
        </Link>
        <p>{dish.description}</p>
        <div className="dish-card-bottom">
          <strong>¥{dish.price.toFixed(2)}</strong>
          <button type="button" className="round-add" onClick={() => addItem(dish)}>
            +
          </button>
        </div>
      </div>
    </article>
  );
}
