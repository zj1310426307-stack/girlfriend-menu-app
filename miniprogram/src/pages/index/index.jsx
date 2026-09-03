import { useEffect, useMemo, useRef, useState } from "react";
import Taro from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import {
  bindCurrentCustomerToWeChat,
  DISH_CACHE_MAX_AGE,
  establishCustomerSession,
  getCachedDishes,
  getCoupleScore,
  getDishes,
  getFavoriteRanking,
  getHomeBootstrap,
  getMyOrders,
  getTodayTasks,
  restoreWeChatCustomerSession
} from "../../api";
import DishCard from "../../components/DishCard";
import LoveScoreCard from "../../components/LoveScoreCard";
import AsyncState from "../../components/AsyncState";
import { ROUTES } from "../../config/routes";
import { addToCart } from "../../utils/cart";
import { getAuthenticatedCustomerId, getCustomerId, hasCustomerSession } from "../../utils/customer";
import { readHomeSnapshot } from "../../utils/homeSnapshot";
import { clearInvite, hasInvitePassed, passInvite } from "../../utils/invite";
import { STATUS_TEXT } from "../../utils/status";
import "./index.css";

const BOOTSTRAP_COMPATIBILITY_FALLBACK_STATUS_CODES = new Set([404, 405, 501]);

/** Build the warm-launch state synchronously before React paints the first page frame. */
function createInitialHomeState() {
  const sessionAvailable = hasCustomerSession();
  const customerId = sessionAvailable ? getAuthenticatedCustomerId() : "";
  const snapshot = customerId ? readHomeSnapshot(customerId) : null;
  return {
    sessionAvailable,
    snapshot,
    dishes: snapshot?.dishes || (sessionAvailable ? getCachedDishes({ maxAge: DISH_CACHE_MAX_AGE }) : [])
  };
}

/** Home focuses on a fast decision instead of exposing every product module. */
export default function Index() {
  const [initialHome] = useState(createInitialHomeState);
  const [inviteChecked, setInviteChecked] = useState(initialHome.sessionAvailable);
  const [invitePassed, setInvitePassed] = useState(initialHome.sessionAvailable);
  const [inviteCode, setInviteCode] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [dishes, setDishes] = useState(initialHome.dishes);
  const [ranking, setRanking] = useState(initialHome.snapshot?.favorite_ranking || []);
  const [coupleScore, setCoupleScore] = useState(initialHome.snapshot?.couple_score || null);
  const [todayTasks, setTodayTasks] = useState(initialHome.snapshot?.today_tasks || null);
  const [recentOrder, setRecentOrder] = useState(initialHome.snapshot?.recent_order || null);
  const [loading, setLoading] = useState(initialHome.sessionAvailable);
  const [error, setError] = useState("");
  const homeRequestInFlightRef = useRef(false);

  /** Own the home request so duplicate effects cannot start competing refreshes. */
  const loadDishes = async () => {
    if (homeRequestInFlightRef.current) return;
    homeRequestInFlightRef.current = true;
    setLoading(true);
    setError("");
    try {
      try {
        const bootstrap = await getHomeBootstrap();
        setDishes(bootstrap.dishes);
        setRanking(bootstrap.favorite_ranking);
        setCoupleScore(bootstrap.couple_score);
        setTodayTasks(bootstrap.today_tasks);
        setRecentOrder(bootstrap.recent_order);
      } catch (bootstrapError) {
        if (bootstrapError?.statusCode === 401) throw bootstrapError;
        const compatibilityFallback = bootstrapError?.code === "BOOTSTRAP_SCHEMA_MISMATCH"
          || BOOTSTRAP_COMPATIBILITY_FALLBACK_STATUS_CODES.has(bootstrapError?.statusCode);
        if (!compatibilityFallback) throw bootstrapError;
        const customerId = getCustomerId();
        const dishPromise = getDishes();
        const secondaryPromises = [
          getFavoriteRanking(customerId),
          getCoupleScore(customerId),
          getTodayTasks(customerId),
          getMyOrders(customerId)
        ];
        const secondaryResultPromise = Promise.allSettled(secondaryPromises);
        setDishes(await dishPromise);
        const [rankingResult, scoreResult, taskResult, orderResult] = await secondaryResultPromise;
        setRanking(rankingResult.status === "fulfilled" ? rankingResult.value : []);
        setCoupleScore(scoreResult.status === "fulfilled" ? scoreResult.value : null);
        setTodayTasks(taskResult.status === "fulfilled" ? taskResult.value : null);
        setRecentOrder(orderResult.status === "fulfilled" ? orderResult.value[0] || null : null);
      }
    } catch (requestError) {
      if (requestError?.statusCode === 401) {
        // The transport has cleared the rejected bearer. Restart the identity
        // gate so a WeChat-bound user can recover without a stale home state.
        clearInvite();
        Taro.reLaunch({ url: ROUTES.HOME }).catch(() => {
          setInvitePassed(false);
          setInviteError("登录已失效，请重新验证");
        });
        return;
      }
      setError(requestError.message || "菜单暂时走丢了");
    } finally {
      setLoading(false);
      homeRequestInFlightRef.current = false;
    }
  };

  useEffect(() => {
    let active = true;
    const restoreIdentity = async () => {
      if (hasCustomerSession()) {
        if (!hasInvitePassed()) passInvite();
        if (active) setInvitePassed(true);
        bindCurrentCustomerToWeChat().catch((error) => {
          console.info("微信身份后台绑定稍后重试", error?.statusCode || error?.message);
        });
      } else {
        const restored = await restoreWeChatCustomerSession();
        if (restored) {
          passInvite();
          if (active) setInvitePassed(true);
        }
      }
      if (active) setInviteChecked(true);
    };
    restoreIdentity();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (inviteChecked && invitePassed) loadDishes();
  }, [inviteChecked, invitePassed]);

  const submitInvite = async () => {
    const value = inviteCode.trim();
    if (!inviteChecked) return;
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
  const pendingTask = useMemo(
    () => todayTasks?.tasks?.find((task) => task.status !== "completed") || null,
    [todayTasks]
  );
  const openDish = (dish) => Taro.navigateTo({ url: `/pages/detail/index?id=${dish.id}` });
  const openTodayTasks = () => Taro.navigateTo({ url: ROUTES.COUPLE_TASKS });
  const openRecentOrder = () => {
    if (recentOrder) {
      Taro.navigateTo({ url: `${ROUTES.ORDER_DETAIL}?id=${recentOrder.id}` });
      return;
    }
    Taro.switchTab({ url: ROUTES.MENU });
  };
  const addDish = (dish) => {
    addToCart(dish);
    Taro.vibrateShort({ type: "light" }).catch(() => {});
    Taro.showToast({ title: "已放进点菜单", icon: "success" });
  };

  if (!invitePassed) {
    return (
      <View className="page invite-home-page">
        <View className="invite-home-card">
          <View className="invite-mark"><Text>GF</Text></View>
          <Text className="eyebrow">PRIVATE KITCHEN</Text>
          <Text className="invite-title">欢迎回到我们的小厨房</Text>
          <Text className="invite-desc">
            {inviteChecked ? "输入邀请码，看看今天最想吃什么。" : "正在连接你的微信身份，页面已经先准备好了。"}
          </Text>
          <Input
            className="invite-input"
            value={inviteCode}
            disabled={!inviteChecked || inviteSubmitting}
            password
            placeholder={inviteChecked ? "请输入邀请码" : "正在恢复身份…"}
            confirmType="done"
            onInput={(event) => { setInviteCode(event.detail.value); setInviteError(""); }}
            onConfirm={submitInvite}
          />
          {inviteError && <Text className="invite-error">{inviteError}</Text>}
          <View className={`invite-button ${(!inviteChecked || inviteSubmitting) ? "disabled" : ""}`} onClick={submitInvite}>
            <Text>{!inviteChecked ? "正在连接微信…" : inviteSubmitting ? "正在验证…" : "进入小厨房"}</Text>
          </View>
        </View>
      </View>
    );
  }

  const hasHomeContent = Boolean(dishes.length || coupleScore || todayTasks || recentOrder);
  const showHomeSections = hasHomeContent || (!loading && !error);

  return (
    <View className="page v2-home-page">
      <View className="v2-home-hero">
        <Text className="eyebrow">TODAY'S KITCHEN</Text>
        <Text className="v2-home-title">你好，今天想吃什么？</Text>
        <Text className="v2-home-subtitle">先挑一道最心动的，剩下的慢慢选。</Text>
        <View className="v2-hero-actions">
          <View onClick={() => Taro.switchTab({ url: ROUTES.MENU })}><Text>看看完整菜单</Text></View>
          <View onClick={() => Taro.switchTab({ url: ROUTES.ORDERS })}><Text>我的点菜单</Text></View>
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

      {loading && hasHomeContent && (
        <View className="v3-home-sync"><Text>正在同步最新内容…</Text></View>
      )}
      {loading && !hasHomeContent && (
        <View className="v3-home-skeleton" aria-label="正在准备今天的菜单">
          <View className="v3-skeleton-line is-title" />
          <View className="v3-skeleton-card" />
          <View className="v3-skeleton-line" />
          <View className="v3-skeleton-summary" />
        </View>
      )}
      {error && hasHomeContent && (
        <View className="v3-home-notice" onClick={loadDishes}>
          <Text>当前显示上次内容，点这里重新同步</Text>
        </View>
      )}
      {error && !hasHomeContent && <AsyncState type="error" message={error} onRetry={loadDishes} />}

      {showHomeSections && (
        <>
          <View className="v2-section-heading"><View><Text>智能推荐</Text><Text>先从今天最值得期待的开始</Text></View></View>
          {recommendations[0] ? (
            <DishCard dish={recommendations[0]} onOpen={openDish} onAdd={addDish} />
          ) : <AsyncState type="empty" message="还没有可推荐的菜" />}

          <View className="v2-section-heading"><View><Text>今日任务</Text><Text>一起完成一件小事</Text></View></View>
          <View className="v3-home-summary" onClick={openTodayTasks}>
            <View>
              <Text>{pendingTask?.title || (todayTasks ? "今天的任务已经全部完成" : "今日任务稍后同步")}</Text>
              <Text>{todayTasks ? `${todayTasks.completed_count}/${todayTasks.total_count} 已完成${pendingTask ? ` · 完成 +${pendingTask.reward_score}` : ""}` : "进入任务页可以重新加载"}</Text>
            </View>
            <Text className="v3-home-action">{pendingTask ? "去完成 ›" : "查看 ›"}</Text>
          </View>

          <View className="v2-section-heading"><View><Text>最近订单</Text><Text>进度一眼就能看见</Text></View></View>
          <View className="v3-home-summary" onClick={openRecentOrder}>
            <View>
              <Text>{recentOrder ? `点菜单 #${recentOrder.id}` : "还没有点过菜"}</Text>
              <Text>{recentOrder ? `${recentOrder.items.map((item) => item.dish_name).join("、")} · ${STATUS_TEXT[recentOrder.status] || recentOrder.status}` : "从今日推荐开始第一单吧"}</Text>
            </View>
            <Text className="v3-home-action">{recentOrder ? "看进度 ›" : "去点菜 ›"}</Text>
          </View>
        </>
      )}
    </View>
  );
}
