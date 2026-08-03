import { Component } from "react";

export default class AppErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error("页面渲染失败", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="app-error-page" role="alert">
        <span className="success-heart">♥</span>
        <h1>页面刚刚走神了</h1>
        <p>点一下重新打开，菜单和点菜清单都还在。</p>
        <button className="primary-button" type="button" onClick={() => window.location.reload()}>
          重新打开
        </button>
      </main>
    );
  }
}
