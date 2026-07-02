import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createDish, deleteDish, getDishes, resolveImageUrl, updateDish, uploadImage } from "../api";

const EMPTY_FORM = { name: "", category: "", price: "", description: "", image_url: "" };

export default function DishManage() {
  const [dishes, setDishes] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = () => getDishes().then(setDishes).catch(() => setError("菜品加载失败。"));
  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setImageFile(null);
    setShowForm(true);
  };

  const openEdit = (dish) => {
    setEditingId(dish.id);
    setForm({
      name: dish.name,
      category: dish.category,
      price: dish.price,
      description: dish.description,
      image_url: dish.image_url,
    });
    setImageFile(null);
    setShowForm(true);
  };

  const save = async (event) => {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      let imageUrl = form.image_url.trim();
      if (imageFile) {
        const uploaded = await uploadImage(imageFile);
        imageUrl = uploaded.image_url;
      }
      const data = { ...form, image_url: imageUrl, price: Number(form.price) };
      if (editingId) await updateDish(editingId, data);
      else await createDish(data);
      setShowForm(false);
      await load();
    } catch {
      setError("保存失败，请确认图片格式、大小和填写内容。");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (dish) => {
    if (!window.confirm(`确定删除“${dish.name}”吗？`)) return;
    try {
      await deleteDish(dish.id);
      setDishes((list) => list.filter((item) => item.id !== dish.id));
    } catch {
      setError("删除失败，请稍后重试。");
    }
  };

  return (
    <section className="content admin-page">
      <div className="admin-heading">
        <div>
          <Link to="/admin" className="back-link">← 返回订单</Link>
          <h1>菜品管理</h1>
        </div>
        <button className="primary-button compact" type="button" onClick={openCreate}>+ 新增菜品</button>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="manage-list">
        {dishes.map((dish) => (
          <article key={dish.id}>
            {dish.image_url ? <img src={resolveImageUrl(dish.image_url)} alt="" /> : <div className="manage-thumb">🍳</div>}
            <div>
              <strong>{dish.name}</strong>
              <p>{dish.category} · ¥{dish.price.toFixed(2)}</p>
            </div>
            <div className="manage-actions">
              <button type="button" onClick={() => openEdit(dish)}>编辑</button>
              <button type="button" className="danger" onClick={() => remove(dish)}>删除</button>
            </div>
          </article>
        ))}
      </div>
      {showForm && (
        <div className="modal-backdrop" onMouseDown={() => setShowForm(false)}>
          <form className="dish-form" onSubmit={save} onMouseDown={(e) => e.stopPropagation()}>
            <div className="form-title">
              <h2>{editingId ? "编辑菜品" : "新增菜品"}</h2>
              <button type="button" onClick={() => setShowForm(false)}>×</button>
            </div>
            <div className="form-row">
              <label>菜名<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
              <label>分类<input required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></label>
            </div>
            <label>价格（元）<input required min="0" step="0.01" type="number" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></label>
            <label>菜品介绍<textarea rows="3" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
            <label className="upload-field">
              上传图片
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                onChange={(e) => setImageFile(e.target.files?.[0] || null)}
              />
              <small>{imageFile ? `已选择：${imageFile.name}` : "支持 JPG、PNG、WEBP，最大 5MB"}</small>
            </label>
            <div className="image-or"><span>或者</span></div>
            <label>手动填写图片地址<input type="text" placeholder="https://... 或 /uploads/..." value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} /></label>
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? "正在保存…" : "保存菜品"}
            </button>
          </form>
        </div>
      )}
    </section>
  );
}
