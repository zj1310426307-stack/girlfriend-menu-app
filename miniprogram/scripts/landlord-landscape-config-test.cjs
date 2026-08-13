const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const read = (...segments) => fs.readFileSync(path.resolve(ROOT, ...segments), "utf8");

const config = JSON.parse(read("dist", "pages", "games", "landlord", "index.json"));
assert.equal(config.pageOrientation, "landscape", "斗地主页面必须编译为横屏");
assert.equal(config.navigationStyle, "custom", "斗地主横屏页必须使用自定义导航");
assert.equal(config.disableScroll, true, "牌桌页面不能产生整页滚动");

const jsx = read("src", "pages", "games", "landlord", "index.jsx");
for (const marker of ["PageMeta", "ll-lobby-settings", "ll-opponents", "ll-action-zone", "LandlordHand", "useHint"]) {
  assert(jsx.includes(marker), `斗地主页面缺少结构：${marker}`);
}
assert(jsx.includes('aria-label="开始斗地主"'), "斗地主开始按钮缺少稳定可访问点击目标");
assert(jsx.includes('<Button\n          className="ll-main-button"') && jsx.includes('disabled={Boolean(busy)}'), "斗地主开局入口必须使用可禁用的原生微信按钮");
assert(jsx.includes('openType="share"'), "斗地主等待牌桌缺少一键邀请入口");
assert(jsx.includes("canPass") && jsx.includes("先选牌"), "斗地主操作栏缺少合法不出状态或选牌指引");
assert(/if \(!roomCode\) return \(\s*<>\s*<PageMeta[^>]*\/>\s*<View className="ll-page ll-lobby">/.test(jsx), "PageMeta 不能作为斗地主 Grid 的子项占用首个格子");

const pageCss = read("src", "pages", "games", "landlord", "index.css");
for (const marker of ["100vw", "100vh", "safe-area-inset-left", "grid-template-columns", "@media (max-height: 330px)"]) {
  assert(pageCss.includes(marker), `斗地主横屏样式缺少：${marker}`);
}
assert(pageCss.includes("@media (max-height:280px)"), "极矮横屏设备缺少大厅压缩布局");
assert(pageCss.includes(".ll-hero { position:relative; z-index:1; grid-column:1; grid-row:1;") && pageCss.includes(".ll-lobby-card { position:relative; z-index:1; grid-column:2; grid-row:1;"), "斗地主主视觉和开局卡必须固定在同一行，避免按钮被挤出视口");
assert(jsx.indexOf('className="ll-main-button"') < jsx.indexOf('className="ll-lobby-settings"'), "斗地主开局按钮必须位于设置项之前，确保低高度横屏也能直接触达");
assert(pageCss.includes("max-height:calc(100vh - 24px)") && pageCss.includes(".ll-main-button::after { border:0; }"), "斗地主配置卡和原生开局按钮缺少横屏视口保护");
assert(pageCss.includes("white-space:nowrap"), "斗地主主标题必须在常见横屏宽度保持单行");

const handCss = read("src", "components", "LandlordHand.css");
const cardCss = read("src", "components", "LandlordCard.css");
assert(handCss.includes("margin-left:-25px"), "手牌没有横屏扇形叠放规则");
assert(cardCss.includes(".ll-card.selected"), "手牌没有选中抬起反馈");

console.log("[landlord] PASS compiled landscape config");
console.log("[landlord] PASS lobby, table, opponents, actions and hand hierarchy");
