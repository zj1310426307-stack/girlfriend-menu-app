export default function CategoryTabs({ categories, active, onChange }) {
  return (
    <div className="category-tabs">
      {["全部", ...categories].map((category) => (
        <button
          type="button"
          key={category}
          className={active === category ? "active" : ""}
          onClick={() => onChange(category)}
        >
          {category}
        </button>
      ))}
    </div>
  );
}
