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

const chessBoard = read("src/components/ChessBoard.jsx");
assert(chessBoard.includes("chess-point"), "象棋必须把棋子放在交叉点而不是方格中央");
assert(chessBoard.includes("data-board-x") && chessBoard.includes("data-board-y"), "象棋点击必须保留服务端坐标");
const chessBoardCss = read("src/components/ChessBoard.css");
assert(chessBoardCss.includes("width:82%") && chessBoardCss.includes("margin:5.5% auto"), "象棋线网四周必须为边缘棋子保留完整显示空间");
assert(chessBoard.includes("chess-file") && chessBoard.includes('vertical full') && chessBoard.includes('vertical top') && chessBoard.includes('vertical bottom'), "象棋竖线必须使用真实上下线段，河界两侧边线必须贯通");
assert(chessBoardCss.includes(".chess-line.vertical.full") && chessBoardCss.includes("background:transparent"), "象棋河界不能用不透明背景遮挡竖线");
assert(chessBoardCss.includes("width:3px") && chessBoardCss.includes("background:#704018"), "象棋线网必须使用真机可见的高对比度粗线");

const flightBoard = read("src/components/FlightBoard.jsx");
assert(flightBoard.includes("trackStyle"), "飞行棋必须使用环形航线而不是单调方框跑道");
assert(flightBoard.includes("flight-event-name"), "飞行棋互动格必须有明确语义");
assert(flightBoard.includes('24: "美食"'), "飞行棋第 24 格必须与服务端 FOOD 事件语义一致");

const animalPage = read("src/pages/games/animal/index.jsx");
assert(animalPage.includes("pendingMove"), "斗兽棋网络等待期间缺少即时落点反馈");
assert(animalPage.includes("GameTurnGuide"), "斗兽棋必须把下一步操作放在棋盘前");

const chessPage = read("src/pages/games/chess/index.jsx");
assert(chessPage.includes("GameTurnGuide") && chessPage.includes("pendingMove"), "象棋必须提供棋盘前指引和提交中落点反馈");

const flightPage = read("src/pages/games/flight/index.jsx");
assert(flightPage.indexOf("<GameTurnGuide") < flightPage.indexOf("<FlightBoard"), "飞行棋必须在棋盘前展示当前操作");
assert(flightPage.indexOf("<DiceButton") < flightPage.indexOf("<FlightBoard"), "飞行棋掷骰入口必须位于棋盘前");

const landlordPage = read("src/pages/games/landlord/index.jsx");
assert(landlordPage.includes("canPass") && landlordPage.includes("先选牌"), "斗地主必须区分可不出状态并提示先选牌");

const polling = read("src/hooks/useAdaptiveGamePolling.js");
assert(polling.includes("maxInterval"), "轮询缺少失败退避上限");
assert(polling.includes("onStatus"), "轮询缺少连接状态回调");

const recovery = read("src/utils/gameRecovery.js");
assert(recovery.includes("reconnectGame"), "恢复流程没有使用持久重连凭证");
assert(recovery.includes("loadState"), "旧房间缺少鉴权状态回退");

const api = read("src/api/index.js");
assert(api.includes("preserveSession"), "过期房间凭证不应清除设备登录");

console.log("game longevity UI/recovery contract: PASS");
