import { useCallback, useEffect, useState } from "react";
import Taro, { usePullDownRefresh } from "@tarojs/taro";
import { Image, Input, Text, Textarea, View } from "@tarojs/components";

import {
  createAdminDish,
  deleteAdminDish,
  getDishes,
  resolveImageUrl,
  updateAdminDish,
  uploadAdminImage
} from "../../api";
import AdminNav from "../../components/AdminNav";
import { clearAdminToken, getAdminToken } from "../../utils/admin";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const EMPTY_FORM = {
  name: "",
  category: "",
  price: "",
  description: "",
  image_url: ""
};

export default function AdminDishesPage() {
  const [dishes, setDishes] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const token = getAdminToken();

  const leaveToLogin = useCallback(() => {
    clearAdminToken();
    Taro.reLaunch({ url: "/pages/admin-login/index" });
  }, []);

  const load = useCallback(async () => {
    if (!token) return leaveToLogin();
    setLoading(true);
    try {
      setDishes(await getDishes());
      setError("");
    } catch (requestError) {
      setError(requestError.message || "菜品加载失败，请稍后重试");
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [leaveToLogin, token]);

  useEffect(() => {
    if (ensureInvitePassed() && token) load();
    else if (!token) leaveToLogin();
  }, [leaveToLogin, load, token]);

  usePullDownRefresh(load);

  const updateField = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const resetForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  const editDish = (dish) => {
    setEditingId(dish.id);
    setForm({
      name: dish.name,
      category: dish.category,
      price: String(dish.price),
      description: dish.description || "",
      image_url: dish.image_url || ""
    });
    Taro.pageScrollTo({ scrollTop: 0, duration: 260 });
  };

  const chooseAndUpload = async () => {
    if (uploading || saving) return;
    try {
      const result = await Taro.chooseImage({
        count: 1,
        sizeType: ["compressed"],
        sourceType: ["album", "camera"]
      });
      const file = result.tempFiles?.[0];
      const filePath = file?.path || result.tempFilePaths?.[0];
      if (!filePath) return;
      if (file?.size && file.size > 5 * 1024 * 1024) {
        Taro.showToast({ title: "图片不能超过 5MB", icon: "none" });
        return;
      }
      setUploading(true);
      const uploaded = await uploadAdminImage(filePath, token);
      updateField("image_url", uploaded.image_url);
      Taro.showToast({ title: "图片已上传", icon: "success" });
    } catch (requestError) {
      if (/cancel/i.test(requestError?.errMsg || "")) return;
      if (requestError.statusCode === 401) return leaveToLogin();
      Taro.showToast({ title: requestError.message || "图片上传失败", icon: "none" });
    } finally {
      setUploading(false);
    }
  };

  const save = async () => {
    if (saving || uploading) return;
    const price = Number(form.price);
    if (!form.name.trim() || !form.category.trim()) {
      Taro.showToast({ title: "请填写菜名和分类", icon: "none" });
      return;
    }
    if (!Number.isFinite(price) || price < 0) {
      Taro.showToast({ title: "请填写正确价格", icon: "none" });
      return;
    }
    const payload = {
      name: form.name.trim(),
      category: form.category.trim(),
      price,
      description: form.description.trim(),
      image_url: form.image_url.trim()
    };
    setSaving(true);
    try {
      if (editingId) await updateAdminDish(editingId, payload, token);
      else await createAdminDish(payload, token);
      Taro.showToast({ title: editingId ? "菜品已更新" : "菜品已新增", icon: "success" });
      resetForm();
      await load();
    } catch (requestError) {
      if (requestError.statusCode === 401) return leaveToLogin();
      Taro.showToast({ title: requestError.message || "保存失败", icon: "none" });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (dish) => {
    const dialog = await Taro.showModal({
      title: "下架这道菜？",
      content: `${dish.name} 将不再出现在点菜页，旧订单记录会保留。`,
      confirmText: "确认下架",
      confirmColor: "#c9506a"
    });
    if (!dialog.confirm) return;
    try {
      await deleteAdminDish(dish.id, token);
      setDishes((current) => current.filter((item) => item.id !== dish.id));
      if (editingId === dish.id) resetForm();
      Taro.showToast({ title: "已下架", icon: "success" });
    } catch (requestError) {
      if (requestError.statusCode === 401) return leaveToLogin();
      Taro.showToast({ title: requestError.message || "下架失败", icon: "none" });
    }
  };

  return (
    <View className="admin-dishes-page">
      <AdminNav active="dishes" />
      <View className="dish-admin-head">
        <Text className="dish-admin-kicker">MENU STUDIO</Text>
        <Text className="dish-admin-title">把想做的菜放进菜单</Text>
        <Text className="dish-admin-desc">支持上传照片，也可以继续填写网络图片链接。</Text>
      </View>

      <View className="dish-form-card">
        <View className="dish-form-title">
          <Text>{editingId ? "编辑菜品" : "新增菜品"}</Text>
          {editingId && <Text onClick={resetForm}>取消编辑</Text>}
        </View>
        <View className="dish-field-row">
          <View className="dish-field"><Text>菜名</Text><Input value={form.name} maxlength={100} placeholder="例如：鱼香肉丝" onInput={(event) => updateField("name", event.detail.value)} /></View>
          <View className="dish-field"><Text>分类</Text><Input value={form.category} maxlength={50} placeholder="肉肉 / 蔬菜" onInput={(event) => updateField("category", event.detail.value)} /></View>
        </View>
        <View className="dish-field"><Text>价格（元）</Text><Input value={form.price} type="digit" placeholder="0.00" onInput={(event) => updateField("price", event.detail.value)} /></View>
        <View className="dish-field"><Text>菜品介绍</Text><Textarea value={form.description} maxlength={1000} placeholder="写一点她看到就会想吃的介绍" onInput={(event) => updateField("description", event.detail.value)} /></View>
        <View className="dish-field"><Text>图片链接</Text><Input value={form.image_url} maxlength={500} placeholder="可手动填写 https://..." onInput={(event) => updateField("image_url", event.detail.value)} /></View>
        <View className="dish-image-tools">
          <View className={`dish-upload-button ${uploading ? "is-disabled" : ""}`} onClick={chooseAndUpload}><Text>{uploading ? "正在上传…" : "从相册或相机上传"}</Text></View>
          {form.image_url && <Image className="dish-image-preview" src={resolveImageUrl(form.image_url)} mode="aspectFill" />}
        </View>
        <View className={`dish-save-button ${(saving || uploading) ? "is-disabled" : ""}`} onClick={save}>
          <Text>{saving ? "正在保存…" : editingId ? "保存修改" : "加入今日菜单"}</Text>
        </View>
      </View>

      <View className="dish-list-heading"><Text>当前菜单</Text><Text>{dishes.length} 道菜</Text></View>
      {loading && <View className="dish-admin-state"><Text>正在整理菜单…</Text></View>}
      {error && <View className="dish-admin-state error" onClick={load}><Text>{error}</Text><Text>点这里重试</Text></View>}
      {!loading && !error && dishes.length === 0 && <View className="dish-admin-state"><Text>菜单还是空的，先新增一道菜吧。</Text></View>}
      <View className="dish-admin-list">
        {dishes.map((dish) => (
          <View className="dish-admin-card" key={dish.id}>
            {dish.image_url
              ? <Image className="dish-admin-photo" src={resolveImageUrl(dish.image_url)} mode="aspectFill" lazyLoad />
              : <View className="dish-admin-photo dish-admin-placeholder"><Text>菜</Text></View>}
            <View className="dish-admin-copy">
              <View><Text>{dish.name}</Text><Text>{dish.category}</Text></View>
              <Text className="dish-admin-description">{dish.description || "还没有菜品介绍"}</Text>
              <Text className="dish-admin-price">¥{Number(dish.price).toFixed(2)}</Text>
              <View className="dish-admin-buttons">
                <View onClick={() => editDish(dish)}><Text>编辑</Text></View>
                <View onClick={() => remove(dish)}><Text>下架</Text></View>
              </View>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}
