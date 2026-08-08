import { useEffect, useMemo, useState } from "react";
import Taro from "@tarojs/taro";
import { Image, Input, ScrollView, Text, View } from "@tarojs/components";

import { getDishes, resolveImageUrl } from "../../api";
import { addToCart } from "../../utils/cart";
import { hasInvitePassed, INVITE_CODE, passInvite } from "../../utils/invite";
import "./index.css";

export default function Index() {
  const [inviteChecked, setInviteChecked] = useState(false);
  const [invitePassed, setInvitePassed] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [dishes, setDishes] = useState([]);
  const [category, setCategory] = useState("全部");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [failedImages, setFailedImages] = useState({});

  // Load the menu only after the invite state has been checked.
  const loadDishes = () => {
    setLoading(true);
    setError("");
    getDishes()
      .then(setDishes)
      .catch((err) => setError(err.message || "菜单暂时走丢了"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setInvitePassed(hasInvitePassed());
    setInviteChecked(true);
  }, []);

  useEffect(() => {
    if (!inviteChecked || !invitePassed) return;
    loadDishes();
  }, [inviteChecked, invitePassed]);

  // Validate the invite code and unlock the menu for this device.
  const submitInvite = () => {
    const value = inviteCode.trim();
    if (!value) {
      setInviteError("先输入邀请码哦");
      return;
    }
    if (value !== INVITE_CODE) {
      setInviteError("邀请码不对，再确认一下");
      return;
    }
    passInvite();
    setInvitePassed(true);
  };

  const categories = useMemo(
    () => ["全部", ...Array.from(new Set(dishes.map((dish) => dish.category)))],
    [dishes]
  );
  const visibleDishes =
    category === "全部" ? dishes : dishes.filter((dish) => dish.category === category);

  const goDetail = (id) => {
    Taro.navigateTo({ url: `/pages/detail/index?id=${id}` });
  };

  const openDiceGame = () => {
    Taro.navigateTo({ url: "/pages/dice/index" }).catch((error) => {
      const detail = error?.errMsg || error?.message || String(error);
      console.error("打开骰子模块失败", detail);
      Taro.showModal({
        title: "骰子模块没有打开",
        content: `当前版本 v1.0.19\n${detail}`,
        showCancel: false,
      });
    });
  };

  const addDish = (event, dish) => {
    event?.stopPropagation?.();
    addToCart(dish);
    Taro.showToast({ title: "已加入点菜清单", icon: "success" });
  };

  if (!inviteChecked) {
    return (
      <View className="page startup-page">
        <View className="startup-card">
          <Text className="startup-heart">♥</Text>
          <Text className="startup-text">正在打开专属菜单…</Text>
        </View>
      </View>
    );
  }

  if (!invitePassed) {
    return (
      <View className="page invite-home-page">
        <View className="invite-home-card">
          <View className="invite-heart">
            <Text>♥</Text>
          </View>
          <Text className="eyebrow">PRIVATE MENU</Text>
          <Text className="invite-title">女朋友专属点菜单</Text>
          <Text className="invite-desc">输入邀请码后，就可以进入今天的菜单啦。</Text>

          <Input
            className="invite-input"
            value={inviteCode}
            password
            placeholder="请输入邀请码"
            confirmType="done"
            onInput={(event) => {
              setInviteCode(event.detail.value);
              setInviteError("");
            }}
            onConfirm={submitInvite}
          />

          {inviteError && <Text className="invite-error">{inviteError}</Text>}

          <View className="invite-button" onClick={submitInvite}>
            <Text>进入点菜页</Text>
          </View>
        </View>
      </View>
    );
  }

  return (
    <View className="page">
      <View className="hero">
        <Text className="eyebrow">TODAY'S MENU</Text>
        <Text className="hero-title">今天想吃什么呀？</Text>
        <Text className="hero-desc">你负责点菜，我负责把喜欢放进每一道菜里。</Text>
        <View className="secondary-button hero-action" onClick={() => Taro.navigateTo({ url: "/pages/my-orders/index" })}>
          <Text>♥ 我的点菜单</Text>
        </View>
      </View>

      <View className="home-section-head">
        <View><Text>甜蜜小工具</Text><Text>决定不了的事，交给一点好运</Text></View>
      </View>

      <View className="home-tool-grid">
        <View className="home-tool-card wheel-home-entry" onClick={() => Taro.navigateTo({ url: "/pages/wheel/index" })}>
          <View className="home-tool-icon"><Text>转</Text></View>
          <Text className="home-tool-title">今晚转盘</Text>
          <Text className="home-tool-desc">自己添加选项，转出今晚答案</Text>
        </View>
        <View className="home-tool-card admin-home-entry" onClick={() => Taro.navigateTo({ url: "/pages/admin-login/index" })}>
          <View className="home-tool-icon"><Text>厨</Text></View>
          <Text className="home-tool-title">小厨房管理</Text>
          <Text className="home-tool-desc">实时看她点了什么、几点想吃</Text>
        </View>
      </View>

      <View className="home-section-head game-section-head">
        <View><Text>一起玩一局</Text><Text>单机练习或和女朋友实时对战</Text></View>
      </View>

      <View
        className="dice-entry card"
        onClick={openDiceGame}
      >
        <View className="dice-entry-icon">
          <Text>⚄</Text>
        </View>
        <View className="dice-entry-copy">
          <Text className="dice-entry-title">3D 大话骰 · 吹牛</Text>
          <Text className="dice-entry-desc">原生酒吧桌面、上滑开盅和 AI 对局 · v1.0.19</Text>
        </View>
        <Text className="dice-entry-arrow">›</Text>
      </View>

      <View
        className="dice-entry dice-online-entry card"
        onClick={() => Taro.navigateTo({ url: "/pages/dice-online/index" })}
      >
        <View className="dice-entry-icon"><Text>♥</Text></View>
        <View className="dice-entry-copy">
          <Text className="dice-entry-title">和女朋友实时对战</Text>
          <Text className="dice-entry-desc">创建双人房间，实时叫骰和开盅</Text>
        </View>
        <Text className="dice-entry-arrow">›</Text>
      </View>

      <View className="menu-section-head">
        <View><Text>今天的菜单</Text><Text>{dishes.length ? `${dishes.length} 道认真准备的菜` : "挑一道今天想吃的"}</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/cart/index" })}><Text>查看清单</Text></View>
      </View>

      <ScrollView className="category-tabs" scrollX>
        {categories.map((item) => (
          <View
            key={item}
            className={`category-tab ${category === item ? "active" : ""}`}
            onClick={() => setCategory(item)}
          >
            <Text>{item}</Text>
          </View>
        ))}
      </ScrollView>

      {loading && <View className="state-box">正在翻开菜单…</View>}
      {error && (
        <View className="state-box error">
          <Text>{error}</Text>
          <View className="retry-button" onClick={loadDishes}>
            <Text>重新加载菜单</Text>
          </View>
        </View>
      )}

      {!loading && !error && (
        <View className="dish-list">
          {visibleDishes.map((dish) => (
            <View className="dish-card card" key={dish.id} onClick={() => goDetail(dish.id)}>
              {dish.image_url && !failedImages[dish.id] ? (
                <Image
                  className="dish-image"
                  src={resolveImageUrl(dish.image_url)}
                  mode="aspectFill"
                  lazyLoad
                  onError={() => setFailedImages((current) => ({ ...current, [dish.id]: true }))}
                />
              ) : (
                <View className="dish-placeholder">🍲</View>
              )}
              <View className="dish-body">
                <View className="dish-top">
                  <Text className="dish-name">{dish.name}</Text>
                  <Text className="dish-category">{dish.category}</Text>
                </View>
                <Text className="dish-desc">{dish.description || "今天也很适合吃这道菜。"}</Text>
                <View className="dish-bottom">
                  <Text className="dish-price">¥{Number(dish.price).toFixed(2)}</Text>
                  <View className="add-button" onClick={(event) => addDish(event, dish)}>
                    <Text>+</Text>
                  </View>
                </View>
              </View>
            </View>
          ))}
        </View>
      )}

      {!loading && !error && visibleDishes.length === 0 && (
        <View className="state-box">这个分类还没有菜，换一个看看吧。</View>
      )}

      <View className="cart-fab" onClick={() => Taro.navigateTo({ url: "/pages/cart/index" })}>
        <Text>点菜清单</Text>
      </View>
    </View>
  );
}
