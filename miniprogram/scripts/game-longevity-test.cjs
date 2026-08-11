const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(ROOT, relative), "utf8");

const hub = read("src/pages/games/index.jsx");
for (const gameType of ["gomoku", "aeroplane", "landlord", "jungle", "chinese_chess", "dice"]) {
  assert(hub.includes(`type: "${gameType}"`), `游戏大厅缺少 ${gameType}`);
}
assert(hub.includes("&resume=1"), "继续游戏必须带明确恢复标记");
assert(!hub.includes("createGameRoom"), "游戏大厅不应同时承担单个游戏的建房逻辑");

for (const page of ["flight", "landlord", "animal", "chess"]) {
  const source = read(`src/pages/games/${page}/index.jsx`);
  assert(source.includes("GameSyncBar"), `${page} 缺少常驻连接状态`);
  assert(source.includes("recoverGameRoom"), `${page} 缺少房间恢复`);
  assert(source.includes("actionLockRef"), `${page} 缺少同步动作锁`);
}

for (const page of ["animal", "chess"]) {
  const source = read(`src/pages/games/${page}/index.jsx`);
  assert(!source.includes("optimistic: true"), `${page} 仍会渲染未确认的幽灵落子`);
  assert(source.includes("确认认输吗"), `${page} 认输缺少二次确认`);
}

const polling = read("src/hooks/useAdaptiveGamePolling.js");
assert(polling.includes("maxInterval"), "轮询缺少失败退避上限");
assert(polling.includes("onStatus"), "轮询缺少连接状态回调");

const recovery = read("src/utils/gameRecovery.js");
assert(recovery.includes("reconnectGame"), "恢复流程没有使用持久重连凭证");
assert(recovery.includes("loadState"), "旧房间缺少鉴权状态回退");

const api = read("src/api/index.js");
assert(api.includes("preserveSession"), "过期房间凭证不应清除设备登录");

console.log("game longevity UI/recovery contract: PASS");
