import { useEffect, useState } from "react";
import Taro from "@tarojs/taro";
import { Text, View, WebView } from "@tarojs/components";

import { DICE_GAME_URL } from "../../config/dice";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

/**
 * Hosts the complete React/Three.js game inside the ordering mini program.
 * Keeping the 3D engine on the web avoids maintaining a second simplified
 * implementation and preserves PBR, HDR and Rapier physics in one codebase.
 */
export default function DicePage() {
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    setAllowed(ensureInvitePassed());
  }, []);

  if (!allowed) {
    return (
      <View className="dice-webview-loading">
        <Text className="dice-webview-heart">♥</Text>
        <Text>正在返回邀请码页面…</Text>
      </View>
    );
  }

  return (
    <WebView
      className="dice-game-webview"
      src={DICE_GAME_URL}
      onError={() => {
        Taro.showModal({
          title: "游戏桌暂时打不开",
          content: "请检查网络，以及微信后台是否已配置网页业务域名。",
          showCancel: false,
        });
      }}
    />
  );
}
