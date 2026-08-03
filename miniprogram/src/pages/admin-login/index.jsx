import { useEffect, useState } from "react";
import Taro from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import { adminLogin } from "../../api";
import { getAdminToken, saveAdminToken } from "../../utils/admin";
import { ensureInvitePassed, INVITE_CODE } from "../../utils/invite";
import "./index.css";

export default function AdminLoginPage() {
  const [allowed, setAllowed] = useState(false);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const passed = ensureInvitePassed();
    setAllowed(passed);
    if (passed && getAdminToken()) {
      Taro.redirectTo({ url: "/pages/admin-orders/index" });
    }
  }, []);

  const submit = async () => {
    if (submitting) return;
    if (!password.trim()) {
      setError("请输入管理密码");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await adminLogin(password, INVITE_CODE);
      saveAdminToken(result.token);
      Taro.redirectTo({ url: "/pages/admin-orders/index" });
    } catch (requestError) {
      setError(requestError.message || "登录失败，请检查密码");
    } finally {
      setSubmitting(false);
    }
  };

  if (!allowed) return <View />;

  return (
    <View className="mini-admin-login">
      <View className="mini-admin-login-card">
        <View className="mini-admin-lock"><Text>厨</Text></View>
        <Text className="mini-admin-kicker">PRIVATE KITCHEN</Text>
        <Text className="mini-admin-title">进入小厨房</Text>
        <Text className="mini-admin-desc">登录后可以实时看到她点了什么、备注了什么，以及希望几点开饭。</Text>
        <Input
          className="mini-admin-password"
          value={password}
          password
          placeholder="输入管理密码"
          confirmType="done"
          onInput={(event) => { setPassword(event.detail.value); setError(""); }}
          onConfirm={submit}
        />
        {error && <Text className="mini-admin-error">{error}</Text>}
        <View className={`mini-admin-submit ${submitting ? "disabled" : ""}`} onClick={submit}>
          <Text>{submitting ? "正在登录…" : "查看她的点菜单"}</Text>
        </View>
        <Text className="mini-admin-safe">管理密码只保存在本机登录状态中，不会显示在页面上。</Text>
      </View>
    </View>
  );
}
