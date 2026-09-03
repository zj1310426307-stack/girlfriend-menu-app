import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useDidShow, usePullDownRefresh } from "@tarojs/taro";
import { Input, Picker, Text, View } from "@tarojs/components";

import { getAdminOrderPage, rollbackAdminOrderStatus, updateAdminOrderStatus } from "../../api";
import { connectAdminOrders } from "../../api/adminSocket";
import AdminNav from "../../components/AdminNav";
import { clearAdminToken, getAdminToken } from "../../utils/admin";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const STATUSES = ["待接单", "已接单", "制作中", "已完成", "暂时做不了"];
const STATUS_OPTIONS = ["", ...STATUSES];
const EMPTY_FILTERS = { status: "", keyword: "", startDate: "", endDate: "" };
const PAGE_SIZE = 20;
const NEXT_STATUSES = {
  "待接单": ["已接单", "暂时做不了"],
  "已接单": ["制作中", "暂时做不了"],
  "制作中": ["已完成", "暂时做不了"],
  "已完成": [],
  "暂时做不了": []
};
const STATUS_CLASS_NAMES = {
  "待接单": "pending",
  "已接单": "accepted",
  "制作中": "cooking",
  "已完成": "completed",
  "暂时做不了": "unavailable",
};
const LIVE_STATUS_TEXT = {
  online: "实时在线",
  connecting: "正在连接",
  offline: "实时连接已断开"
};

/** Format backend timestamps for the compact order card header. */
function formatTime(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").slice(0, 16);
}

/** Append one cursor page without duplicating orders already on screen. */
function appendUniqueOrders(current, incoming) {
  const existingIds = new Set(current.map((order) => order.id));
  return [...current, ...incoming.filter((order) => !existingIds.has(order.id))];
}

/** Refresh the newest page while retaining older cursor pages already loaded. */
function mergeRefreshedHead(current, incoming) {
  if (!incoming.length) return [];
  const incomingIds = new Set(incoming.map((order) => order.id));
  const oldestIncomingId = incoming[incoming.length - 1].id;
  const olderOrders = current.filter((order) => (
    order.id < oldestIncomingId && !incomingIds.has(order.id)
  ));
  return [...incoming, ...olderOrders];
}

/** Return whether a filter set changes the default all-orders query. */
function hasAnyFilter(filters) {
  return Boolean(filters.status || filters.keyword || filters.startDate || filters.endDate);
}

/** Confirm customer-visible terminal choices before the request is sent. */
async function confirmTerminalStatus(order, status) {
  if (status === "已完成") {
    const confirmation = await Taro.showModal({
      title: "确认完成订单？",
      content: `订单 #${order.id} 完成后不能撤回，她会收到进度并可以评价。`,
      confirmText: "确认完成"
    });
    return confirmation.confirm;
  }
  if (status === "暂时做不了") {
    const confirmation = await Taro.showModal({
      title: "确认暂时做不了？",
      content: `她会看到订单 #${order.id} 的这个结果，之后仍可通过“撤回上一步”恢复。`,
      confirmText: "确认操作"
    });
    return confirmation.confirm;
  }
  return true;
}

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [liveStatus, setLiveStatus] = useState("connecting");
  const [updatingId, setUpdatingId] = useState(null);
  const [nextCursor, setNextCursor] = useState(null);
  const [totalEstimate, setTotalEstimate] = useState(0);
  const [filterDraft, setFilterDraft] = useState(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(EMPTY_FILTERS);
  const readVersionRef = useRef(0);
  const loadingMoreRef = useRef(false);
  const hasExtendedPagesRef = useRef(false);
  const updatingRef = useRef(null);
  const didShowOnceRef = useRef(false);
  const token = getAdminToken();

  const leaveToLogin = useCallback(() => {
    clearAdminToken();
    Taro.redirectTo({ url: "/pages/admin-login/index" });
  }, []);

  /** Invalidate reads started before an order mutation so stale data cannot win. */
  const invalidateReadRequests = useCallback(() => {
    readVersionRef.current += 1;
    setLoading(false);
  }, []);

  /** Load either the applied first page or one explicit cursor page. */
  const load = useCallback(async ({
    silent = false,
    append = false,
    cursor = null,
    preservePages = false
  } = {}) => {
    if (!token) {
      leaveToLogin();
      return;
    }
    if (updatingRef.current) {
      Taro.stopPullDownRefresh();
      return;
    }
    if (silent && !append && loadingMoreRef.current) return;
    if (append) {
      if (!cursor || loadingMoreRef.current) return;
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }

    const requestVersion = readVersionRef.current + 1;
    readVersionRef.current = requestVersion;
    if (!silent) setLoading(true);
    try {
      const data = await getAdminOrderPage(token, {
        limit: PAGE_SIZE,
        ...(append && cursor ? { cursor } : {}),
        ...(appliedFilters.status ? { status: appliedFilters.status } : {}),
        ...(appliedFilters.keyword ? { keyword: appliedFilters.keyword } : {}),
        ...(appliedFilters.startDate ? { start_date: appliedFilters.startDate } : {}),
        ...(appliedFilters.endDate ? { end_date: appliedFilters.endDate } : {})
      });
      if (requestVersion !== readVersionRef.current || updatingRef.current) return;

      const incoming = data.items || [];
      const keepExtendedPages = Boolean(
        preservePages && hasExtendedPagesRef.current && data.next_cursor
      );
      setOrders((current) => {
        if (append) return appendUniqueOrders(current, incoming);
        return keepExtendedPages ? mergeRefreshedHead(current, incoming) : incoming;
      });
      if (append) {
        hasExtendedPagesRef.current = true;
        setNextCursor(data.next_cursor || null);
      } else {
        const nextTotal = Number(data.total_estimate);
        setTotalEstimate(Number.isFinite(nextTotal) ? nextTotal : incoming.length);
        if (!keepExtendedPages) {
          hasExtendedPagesRef.current = false;
          setNextCursor(data.next_cursor || null);
        }
      }
      setError("");
    } catch (requestError) {
      if (requestError.statusCode === 401) {
        leaveToLogin();
        return;
      }
      if (requestVersion !== readVersionRef.current) return;
      const message = requestError.message || "订单加载失败，请稍后重试";
      if (append) {
        Taro.showToast({ title: message, icon: "none" });
      } else {
        setError(message);
      }
    } finally {
      if (append) {
        loadingMoreRef.current = false;
        setLoadingMore(false);
      }
      if (requestVersion === readVersionRef.current) setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [appliedFilters, leaveToLogin, token]);

  useEffect(() => {
    if (!ensureInvitePassed() || !token) {
      if (!token) leaveToLogin();
      return undefined;
    }
    load();
    const live = connectAdminOrders({
      token,
      onEvent: () => load({ silent: true, preservePages: true }),
      onStatus: setLiveStatus
    });
    const timer = setInterval(() => load({ silent: true, preservePages: true }), 12000);
    return () => {
      live.close();
      clearInterval(timer);
    };
  }, [leaveToLogin, load, token]);

  useDidShow(() => {
    if (!didShowOnceRef.current) {
      didShowOnceRef.current = true;
      return;
    }
    if (token) load({ silent: true, preservePages: true });
  });
  usePullDownRefresh(() => load({ preservePages: true }));

  const pendingCount = useMemo(
    () => orders.filter((order) => ["待接单", "已接单", "制作中"].includes(order.status)).length,
    [orders]
  );
  const hasAppliedFilters = useMemo(() => hasAnyFilter(appliedFilters), [appliedFilters]);
  const hasDraftFilters = useMemo(() => hasAnyFilter(filterDraft), [filterDraft]);

  /** Apply the completed filter form as one query, avoiding per-keystroke reloads. */
  const applyFilters = () => {
    if (updatingRef.current) return;
    if (filterDraft.startDate && filterDraft.endDate && filterDraft.startDate > filterDraft.endDate) {
      Taro.showToast({ title: "开始日期不能晚于结束日期", icon: "none" });
      return;
    }
    const normalized = { ...filterDraft, keyword: filterDraft.keyword.trim() };
    setFilterDraft(normalized);
    setAppliedFilters({ ...normalized });
  };

  /** Restore both the visible form and the active query to all orders. */
  const clearFilters = () => {
    if (updatingRef.current || (!hasDraftFilters && !hasAppliedFilters)) return;
    setFilterDraft({ ...EMPTY_FILTERS });
    setAppliedFilters({ ...EMPTY_FILTERS });
  };

  /** Keep the active status-filtered list consistent after one mutation. */
  const mergeUpdatedOrder = useCallback((updated) => {
    const leavesCurrentFilter = Boolean(
      appliedFilters.status && updated.status !== appliedFilters.status
    );
    setOrders((current) => leavesCurrentFilter
      ? current.filter((item) => item.id !== updated.id)
      : current.map((item) => item.id === updated.id ? updated : item));
    if (leavesCurrentFilter) {
      setTotalEstimate((current) => Math.max(0, current - 1));
    }
  }, [appliedFilters.status]);

  /** Move one order forward while serializing all administrator mutations. */
  const changeStatus = async (order, status) => {
    if (!status || status === order.status || updatingRef.current) return;
    updatingRef.current = order.id;
    setUpdatingId(order.id);
    let refreshAfterAction = false;
    try {
      const confirmed = await confirmTerminalStatus(order, status);
      if (!confirmed) return;
      invalidateReadRequests();
      const updated = await updateAdminOrderStatus(order.id, status, token, order.status);
      mergeUpdatedOrder(updated);
      setError("");
      Taro.showToast({ title: `已改为${status}`, icon: "success" });
    } catch (requestError) {
      if (requestError.statusCode === 401) return leaveToLogin();
      if (requestError.statusCode === 409) {
        refreshAfterAction = true;
        Taro.showToast({ title: "订单状态已变化，正在刷新", icon: "none" });
      } else {
        Taro.showToast({ title: requestError.message || "状态修改失败", icon: "none" });
      }
    } finally {
      updatingRef.current = null;
      setUpdatingId(null);
    }
    if (refreshAfterAction) load({ silent: true, preservePages: true });
  };

  /** Roll one order back with the same global lock and conflict recovery. */
  const rollbackStatus = async (order) => {
    if (updatingRef.current || order.status === "已完成") return;
    updatingRef.current = order.id;
    setUpdatingId(order.id);
    let refreshAfterAction = false;
    try {
      const confirmation = await Taro.showModal({
        title: "撤回上一步？",
        content: "撤回会写入状态记录；已完成订单不能撤回。",
        confirmText: "确认撤回"
      });
      if (!confirmation.confirm) return;
      invalidateReadRequests();
      const updated = await rollbackAdminOrderStatus(order.id, token, order.status);
      mergeUpdatedOrder(updated);
      setError("");
      Taro.showToast({ title: "已撤回上一步", icon: "success" });
    } catch (requestError) {
      if (requestError.statusCode === 401) return leaveToLogin();
      if (requestError.statusCode === 409) {
        refreshAfterAction = true;
        Taro.showToast({ title: "订单状态已变化，正在刷新", icon: "none" });
      } else {
        Taro.showToast({ title: requestError.message || "撤回失败", icon: "none" });
      }
    } finally {
      updatingRef.current = null;
      setUpdatingId(null);
    }
    if (refreshAfterAction) load({ silent: true, preservePages: true });
  };

  const controlsLocked = Boolean(updatingId);
  const completedCount = orders.filter((order) => order.status === "已完成").length;
  const statusPickerIndex = Math.max(0, STATUS_OPTIONS.indexOf(filterDraft.status));

  return (
    <View className="mini-admin-page">
      <AdminNav active="orders" />
      <View className="mini-admin-head">
        <View>
          <Text className="mini-admin-kicker">LIVE KITCHEN BOARD</Text>
          <Text className="mini-admin-title">她今天点了什么</Text>
          <Text className="mini-admin-subtitle">新订单会自动出现在这里，下拉也可以立即刷新。</Text>
        </View>
        <View className={`mini-live mini-live-${liveStatus}`}>
          <Text>{LIVE_STATUS_TEXT[liveStatus] || LIVE_STATUS_TEXT.connecting}</Text>
        </View>
      </View>

      <View className="mini-admin-summary">
        <View><Text>{hasAppliedFilters ? "筛选结果" : "全部订单"}</Text><Text>{totalEstimate}</Text></View>
        <View><Text>当前待处理</Text><Text>{pendingCount}</Text></View>
        <View><Text>当前已完成</Text><Text>{completedCount}</Text></View>
      </View>

      <View className="mini-admin-summary mini-admin-filters">
        <Picker
          className="mini-filter-control"
          mode="selector"
          range={["全部状态", ...STATUSES]}
          value={statusPickerIndex}
          disabled={controlsLocked}
          onChange={(event) => setFilterDraft((current) => ({
            ...current,
            status: STATUS_OPTIONS[Number(event.detail.value)]
          }))}
        >
          <View className="mini-filter-card"><Text>状态</Text><Text>{filterDraft.status || "全部状态"}</Text></View>
        </Picker>
        <Input
          className="mini-filter-input"
          value={filterDraft.keyword}
          disabled={controlsLocked}
          placeholder="订单号或菜名"
          onInput={(event) => setFilterDraft((current) => ({ ...current, keyword: event.detail.value }))}
        />
        <View className={`mini-filter-action ${controlsLocked ? "is-disabled" : ""}`} onClick={applyFilters}>
          <Text>筛选</Text><Text>查询</Text>
        </View>
      </View>
      <View className="mini-admin-summary mini-admin-filters">
        <Picker
          className="mini-filter-control"
          mode="date"
          value={filterDraft.startDate}
          end={filterDraft.endDate || "2100-12-31"}
          disabled={controlsLocked}
          onChange={(event) => setFilterDraft((current) => ({ ...current, startDate: event.detail.value }))}
        >
          <View className="mini-filter-card"><Text>开始日期</Text><Text>{filterDraft.startDate || "不限"}</Text></View>
        </Picker>
        <Picker
          className="mini-filter-control"
          mode="date"
          value={filterDraft.endDate}
          start={filterDraft.startDate || "2000-01-01"}
          end="2100-12-31"
          disabled={controlsLocked}
          onChange={(event) => setFilterDraft((current) => ({ ...current, endDate: event.detail.value }))}
        >
          <View className="mini-filter-card"><Text>结束日期</Text><Text>{filterDraft.endDate || "不限"}</Text></View>
        </Picker>
        <View
          className={`mini-filter-action ${controlsLocked || (!hasDraftFilters && !hasAppliedFilters) ? "is-disabled" : ""}`}
          onClick={clearFilters}
        >
          <Text>重置</Text><Text>清空筛选</Text>
        </View>
      </View>

      {loading && <View className="mini-admin-state"><Text>正在翻开她的点菜单…</Text></View>}
      {error && <View className="mini-admin-state error" onClick={() => load({ preservePages: true })}><Text>{error}</Text><Text>点这里重新加载</Text></View>}
      {!loading && !error && orders.length === 0 && (
        <View className="mini-admin-state">
          <Text>{hasAppliedFilters ? "没有找到符合条件的订单。" : "她还没有点菜，先等等她的消息吧。"}</Text>
          {hasAppliedFilters && <Text className="mini-state-action" onClick={clearFilters}>清空筛选，查看全部订单</Text>}
        </View>
      )}

      <View className="mini-order-list">
        {orders.map((order) => {
          const nextStatuses = NEXT_STATUSES[order.status] || [];
          const cardIsUpdating = updatingId === order.id;
          return (
            <View className="mini-order-card" key={order.id}>
              <View className="mini-order-top">
                <View><Text>订单 #{order.id}</Text><Text>{formatTime(order.created_at)}</Text></View>
                <Text className={`mini-status mini-status-${STATUS_CLASS_NAMES[order.status] || "pending"}`}>
                  {order.status}
                </Text>
              </View>
              <View className="mini-order-dishes">
                {order.items.map((item) => (
                  <View key={item.id}><Text>{item.dish_name}</Text><Text>× {item.quantity}</Text></View>
                ))}
              </View>
              <View className="mini-order-meta">
                <View><Text>希望用餐</Text><Text>{order.desired_time || "没有指定时间"}</Text></View>
                <View><Text>她的备注</Text><Text>{order.note || "没有特别备注"}</Text></View>
                <View><Text>爱心评价</Text><Text>{order.has_review ? `${"♥".repeat(order.review?.rating || 0)} ${order.review?.comment || "已评价"}` : "还没有评价"}</Text></View>
              </View>
              <Picker
                mode="selector"
                range={nextStatuses}
                value={0}
                disabled={controlsLocked || !nextStatuses.length}
                onChange={(event) => changeStatus(order, nextStatuses[Number(event.detail.value)])}
              >
                <View className={`mini-status-picker ${controlsLocked ? "is-disabled" : ""}`}>
                  <Text>{cardIsUpdating ? "正在处理…" : controlsLocked ? "请稍候…" : nextStatuses.length ? "推进订单状态" : `当前为${order.status}`}</Text>
                  <Text>⌄</Text>
                </View>
              </Picker>
              {order.status !== "待接单" && order.status !== "已完成" && (
                <View
                  className={`mini-status-picker ${controlsLocked ? "is-disabled" : ""}`}
                  onClick={() => !controlsLocked && rollbackStatus(order)}
                >
                  <Text>{cardIsUpdating ? "正在处理…" : controlsLocked ? "请稍候…" : "撤回上一步"}</Text><Text>↶</Text>
                </View>
              )}
            </View>
          );
        })}
      </View>
      {nextCursor && !loading && !error && (
        <View
          className={`secondary-button ${loadingMore || controlsLocked ? "is-disabled" : ""}`}
          onClick={() => !loadingMore && !controlsLocked && load({ silent: true, append: true, cursor: nextCursor })}
        >
          <Text>{loadingMore ? "正在加载更多…" : "加载更多订单"}</Text>
        </View>
      )}

      <View className="mini-admin-actions">
        <View className={controlsLocked ? "is-disabled" : ""} onClick={() => !controlsLocked && load({ preservePages: true })}><Text>刷新订单</Text></View>
        <View onClick={() => Taro.redirectTo({ url: "/pages/admin-dashboard/index" })}><Text>返回总览</Text></View>
      </View>
    </View>
  );
}
