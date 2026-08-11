const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const babel = require("@babel/core");

const sourcePath = path.resolve(__dirname, "../src/api/gameSocket.js");
const source = fs.readFileSync(sourcePath, "utf8");
const transformed = babel.transformSync(source, {
  filename: sourcePath,
  sourceType: "module",
  configFile: false,
  babelrc: false,
  plugins: ["@babel/plugin-transform-modules-commonjs"]
}).code;

const timeouts = new Map();
const intervals = new Map();
const timeoutDelays = [];
let timerId = 0;

function fakeSetTimeout(callback, delay) {
  const id = ++timerId;
  timeouts.set(id, callback);
  timeoutDelays.push(delay);
  return id;
}

function fakeClearTimeout(id) {
  timeouts.delete(id);
}

function runNextTimeout() {
  const entry = timeouts.entries().next().value;
  assert.ok(entry, "expected a pending reconnect timer");
  const [id, callback] = entry;
  timeouts.delete(id);
  callback();
}

function fakeSetInterval(callback) {
  const id = ++timerId;
  intervals.set(id, callback);
  return id;
}

function fakeClearInterval(id) {
  intervals.delete(id);
}

class FakeSocketTask {
  constructor() {
    this.handlers = {};
    this.sent = [];
    this.closeCalls = [];
  }

  onOpen(handler) { this.handlers.open = handler; }
  onMessage(handler) { this.handlers.message = handler; }
  onError(handler) { this.handlers.error = handler; }
  onClose(handler) { this.handlers.close = handler; }
  send({ data }) { this.sent.push(JSON.parse(data)); }
  close(options) { this.closeCalls.push(options); }
  emitOpen() { this.handlers.open?.(); }
  emitError() { this.handlers.error?.({}); }
  emitClose() { this.handlers.close?.({}); }
}

const tasks = [];
const taro = {
  connectSocket() {
    const task = new FakeSocketTask();
    tasks.push(task);
    return task;
  },
  setStorageSync() {}
};

const fakeMath = Object.create(Math);
fakeMath.random = () => 0.5;
const moduleObject = { exports: {} };
const context = vm.createContext({
  module: moduleObject,
  exports: moduleObject.exports,
  require(request) {
    if (request === "@tarojs/taro") return { __esModule: true, default: taro };
    if (request === "../config/env") return { WEBSOCKET_ORIGIN: "wss://example.test" };
    if (request === "../utils/customer") return { getCustomerToken: () => "customer-token" };
    throw new Error(`Unexpected require: ${request}`);
  },
  setTimeout: fakeSetTimeout,
  clearTimeout: fakeClearTimeout,
  setInterval: fakeSetInterval,
  clearInterval: fakeClearInterval,
  Math: fakeMath,
  console
});
vm.runInContext(transformed, context, { filename: sourcePath });

const { connectGameRoom, createGameSocket } = moduleObject.exports;
assert.equal(createGameSocket, connectGameRoom, "generic socket API alias must remain compatible");

const statuses = [];
const errors = [];
const connection = connectGameRoom({
  roomCode: "ABCD",
  gameType: "gomoku",
  playerName: "tester",
  onStatus: (status) => statuses.push(status),
  onError: (message) => errors.push(message)
});
assert.equal(tasks.length, 1, "initial connection should start immediately");

for (let sequence = 0; sequence < 25; sequence += 1) {
  connection.send({ type: "move", sequence });
}
connection.send({ type: "ping" });
connection.send({ type: "heartbeat" });
tasks[0].emitOpen();

assert.equal(tasks[0].sent[0].type, "join", "join must be sent before queued actions");
const firstFlush = tasks[0].sent.slice(1);
assert.equal(firstFlush.length, 20, "offline queue must be capped at 20 messages");
assert.deepEqual(
  firstFlush.map((message) => message.data.sequence),
  Array.from({ length: 20 }, (_, index) => index + 5),
  "queue should retain the newest 20 actions"
);
assert.ok(firstFlush.every((message) => message.type === "move"), "heartbeats must not enter the queue");

tasks[0].emitClose();
assert.equal(timeoutDelays.at(-1), 1000, "first reconnect should use the base delay");
connection.send({ type: "move", sequence: 100 });
runNextTimeout();
assert.equal(tasks.length, 2, "reconnect timer should create another socket");

tasks[1].emitError();
assert.equal(timeoutDelays.at(-1), 2000, "failed reconnect should exponentially back off");
assert.equal(errors.length, 1, "one outage should not create repeated reconnect alerts");
runNextTimeout();
assert.equal(tasks.length, 3);
tasks[2].emitOpen();
assert.deepEqual(
  tasks[2].sent.map((message) => message.type),
  ["join", "move"],
  "successful reconnect should join then flush pending actions"
);
assert.equal(tasks[2].sent[1].data.sequence, 100);

tasks[2].emitClose();
assert.equal(timeoutDelays.at(-1), 1000, "successful open should reset reconnect backoff");
connection.close();
assert.equal(timeouts.size, 0, "manual close should cancel pending reconnects");
tasks[2].emitClose();
assert.equal(timeouts.size, 0, "manual close should never schedule another reconnect");
assert.equal(connection.send({ type: "move", sequence: 101 }), false, "closed connection rejects sends");

assert.ok(statuses.includes("online"));
assert.ok(statuses.includes("offline"));
console.log("gameSocket reconnect/queue lifecycle: PASS");
