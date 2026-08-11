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

const pageCss = read("src", "pages", "games", "landlord", "index.css");
for (const marker of ["100vw", "100vh", "safe-area-inset-left", "grid-template-columns", "@media (max-height: 330px)"]) {
  assert(pageCss.includes(marker), `斗地主横屏样式缺少：${marker}`);
}

const handCss = read("src", "components", "LandlordHand.css");
const cardCss = read("src", "components", "LandlordCard.css");
assert(handCss.includes("margin-left:-25px"), "手牌没有横屏扇形叠放规则");
assert(cardCss.includes(".ll-card.selected"), "手牌没有选中抬起反馈");

console.log("[landlord] PASS compiled landscape config");
console.log("[landlord] PASS lobby, table, opponents, actions and hand hierarchy");
