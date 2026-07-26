import { Component } from "react";
import { Text, View } from "@tarojs/components";

import "./app.css";

// Keep a visible recovery screen when an unexpected page render error occurs.
class AppErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("小程序页面渲染失败", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <View className="app-error-page">
          <Text className="app-error-heart">♥</Text>
          <Text className="app-error-title">页面没有打开成功</Text>
          <Text className="app-error-desc">请关闭小程序后重新打开，或在微信中清理本小程序缓存。</Text>
        </View>
      );
    }

    return this.props.children;
  }
}

// Wrap every mini-program page with the shared render-error fallback.
export default function App({ children }) {
  return <AppErrorBoundary>{children}</AppErrorBoundary>;
}
