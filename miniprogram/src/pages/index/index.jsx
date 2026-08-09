import { useEffect, useMemo, useState } from "react";
import Taro from "@tarojs/taro";
import { Input, ScrollView, Text, View } from "@tarojs/components";

import { establishCustomerSession, getCoupleScore, getDishes, getFavoriteRanking } from "../../api";
import DishCard from "../../components/DishCard";
import LoveScoreCard from "../../components/LoveScoreCard";
import AsyncState from "../../components/AsyncState";
import { addToCart } from "../../utils/cart";
import { getCustomerId, hasCustomerSession } from "../../utils/customer";
import { hasInvitePassed, passInvite } from "../../utils/invite";
import "./index.css";

/** Home focuses on a fast decision instead of exposing every product module. */
export default function Index() {
  const [inviteChecked, setInviteChecked] = useState(false);
  const [invitePassed, setInvitePassed] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [dishes, setDishes] = useState([]);
  const [ranking, setRanking] = useState([]);
  const [coupleScore, setCoupleScore] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadDishes = async () => {
    setLoading(true);
    setError("");
    try {
      const customerId = getCustomerId();
      const [dishResult, rankingResult, scoreResult] = await Promise.allSettled([
        getDishes(),
        getFavoriteRanking(customerId),
        getCoupleScore(customerId)
      ]);
      if (dishResult.status === "rejected") throw dishResult.reason;
      setDishes(dishResult.value);
      setRanking(rankingResult.status === "fulfilled" ? rankingResult.value : []);
      setCoupleScore(scoreResult.status === "fulfilled" ? scoreResult.value : null);
    } catch (requestError) {
      setError(requestError.message || "菜单暂时走丢了");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setInvitePassed(hasInvitePassed() && hasCustomerSession());
    setInviteChecked(true);
  }, []);

  useEffect(() => {
    if (inviteChecked && invitePassed) loadDishes();
  }, [inviteChecked, invitePassed]);

  const submitInvite = async () => {
    const value = inviteCode.trim();
    if (!value) return setInviteError("先输入邀请码哦");
    if (inviteSubmitting) return;
    setInviteSubmitting(true);
    setInviteError("");
    try {
      await establishCustomerSession(value);
      passInvite();
      setInvitePassed(true);
    } catch (requestError) {
      setInviteError(requestError.message || "验证暂时失败，请稍后再试");
    } finally {
      setInviteSubmitting(false);
    }
  };

  const rankedDishes = useMemo(
    () => ranking.map((rank) => dishes.find((dish) => dish.id === rank.dish_id)).filter(Boolean),
    [dishes, ranking]
  );
  const recommendations = useMemo(() => {
    const rankedIds = new Set(rankedDishes.map((dish) => dish.id));
    return [...rankedDishes, ...dishes.filter((dish) => !rankedIds.has(dish.id))].slice(0, 3);
  }, [dishes, rankedDishes]);
  const recentChoices = useMemo(
    () => (rankedDishes.length ? rankedDishes : dishes.slice(3, 7)),
    [dishes, rankedDishes]
  );
  const todayMenu = useMemo(() => dishes.slice(0, 4), [dishes]);
  const openDish = (dish) => Taro.navigateTo({ url: `/pages/detail/index?id=${dish.id}` });
  const addDish = (dish) => {
    addToCart(dish);
    Taro.vibrateShort({ type: "light" }).catch(() => {});
    Taro.showToast({ title: "已放进点菜单", icon: "success" });
  };

  if (!inviteChecked) {
    return <View className="page startup-page"><Text>正在打开专属菜单…</Text></View>;
  }

  if (!invitePassed) {
    return (
      <View className="page invite-home-page">
        <View className="invite-home-card">
          <View className="invite-mark"><Text>GF</Text></View>
          <Text className="eyebrow">PRIVATE KITCHEN</Text>
          <Text className="invite-title">欢迎回到我们的小厨房</Text>
          <Text className="invite-desc">输入邀请码，看看今天最想吃什么。</Text>
          <Input
            className="invite-input"
            value={inviteCode}
            password
            placeholder="请输入邀请码"
            confirmType="done"
            onInput={(event) => { setInviteCode(event.detail.value); setInviteError(""); }}
            onConfirm={submitInvite}
          />
          {inviteError && <Text className="invite-error">{inviteError}</Text>}
          <View className={`invite-button ${inviteSubmitting ? "disabled" : ""}`} onClick={submitInvite}>
            <Text>{inviteSubmitting ? "正在验证…" : "进入小厨房"}</Text>
          </View>
        </View>
      </View>
    );
  }

  return (
    <View className="page v2-home-page">
      <View className="v2-home-hero">
        <Text className="eyebrow">TODAY'S KITCHEN</Text>
        <Text className="v2-home-title">你好，今天想吃什么？</Text>
        <Text className="v2-home-subtitle">先挑一道最心动的，剩下的慢慢选。</Text>
        <View className="v2-hero-actions">
          <View onClick={() => Taro.switchTab({ url: "/pages/menu/index" })}><Text>看看完整菜单</Text></View>
          <View onClick={() => Taro.switchTab({ url: "/pages/my-orders/index" })}><Text>我的点菜单</Text></View>
        </View>
      </View>

      {coupleScore && (
        <LoveScoreCard
          className="v2-home-love-score"
          summary={coupleScore}
          compact
          onOpen={() => Taro.switchTab({ url: "/pages/couple/index" })}
        />
      )}

      {loading && <AsyncState message="正在准备今天的菜单…" />}
      {error && <AsyncState type="error" message={error} onRetry={loadDishes} />}

      {!loading && !error && (
        <>
          <View className="v2-section-heading"><View><Text>智能推荐</Text><Text>先从今天最值得期待的开始</Text></View></View>
          {recommendations[0] ? (
            <DishCard dish={recommendations[0]} onOpen={openDish} onAdd={addDish} />
          ) : <AsyncState type="empty" message="还没有可推荐的菜" />}

          <View className="v2-section-heading"><View><Text>最近常点</Text><Text>熟悉的味道，选择更快</Text></View></View>
          <ScrollView className="v2-recent-scroll" scrollX enhanced showScrollbar={false}>
            <View className="v2-recent-row">
              {(recentChoices.length ? recentChoices : recommendations).map((dish) => (
                <DishCard key={dish.id} dish={dish} compact onOpen={openDish} onAdd={addDish} />
              ))}
            </View>
          </ScrollView>

          {ranking.length > 0 && (
            <>
              <View className="v2-section-heading"><View><Text>她最喜欢 ♥</Text><Text>综合点单、评价和再次点单</Text></View></View>
              <View className="v2-ranking-card">
                {ranking.map((item, index) => {
                  const dish = dishes.find((candidate) => candidate.id === item.dish_id);
                  return (
                    <View key={item.dish_id} onClick={() => dish && openDish(dish)}>
                      <Text>{index + 1}</Text>
                      <View><Text>{item.name}</Text><Text>点过 {item.count} 次{item.rating ? ` · ${item.rating} 颗爱心` : ""}</Text></View>
                      <Text>{item.is_favorite ? "♥" : "›"}</Text>
                    </View>
                  );
                })}
              </View>
            </>
          )}

          <View className="v2-section-heading v2-heading-with-action">
            <View><Text>今日菜单</Text><Text>{dishes.length} 道可以认真准备的菜</Text></View>
            <Text onClick={() => Taro.switchTab({ url: "/pages/menu/index" })}>查看全部</Text>
          </View>
          <View className="v2-today-list">
            {todayMenu.map((dish) => <DishCard key={dish.id} dish={dish} onOpen={openDish} onAdd={addDish} />)}
          </View>

          <View className="v2-section-heading"><View><Text>快捷入口</Text><Text>点菜和查看进度都在这里</Text></View></View>
          <View className="v2-shortcuts">
            <View onClick={() => Taro.switchTab({ url: "/pages/menu/index" })}><Text>浏览菜单</Text><Text>按分类慢慢挑选</Text></View>
            <View onClick={() => Taro.navigateTo({ url: "/pages/cart/index" })}><Text>当前清单</Text><Text>填写备注并下单</Text></View>
            <View onClick={() => Taro.switchTab({ url: "/pages/my-orders/index" })}><Text>历史订单</Text><Text>查看状态和评价</Text></View>
          </View>
        </>
      )}
    </View>
  );
}
