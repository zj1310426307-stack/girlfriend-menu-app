const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const babel = require("@babel/core");

const sourcePath = path.resolve(__dirname, "../src/api/cloudContainer.js");
const source = fs.readFileSync(sourcePath, "utf8");
const transformed = babel.transformSync(source, {
  filename: sourcePath,
  sourceType: "module",
  configFile: false,
  babelrc: false,
  plugins: ["@babel/plugin-transform-modules-commonjs"]
}).code;

const calls = { init: [], http: [], socket: [] };
const socketTask = { kind: "socket-task" };
const cloud = {
  init(options) { calls.init.push(options); },
  async callContainer(options) {
    calls.http.push(options);
    return { statusCode: 200, data: { ok: true } };
  },
  async connectContainer(options) {
    calls.socket.push(options);
    return { socketTask };
  }
};
const taro = {
  cloud,
  connectSocket() {
    throw new Error("private production transport must not open a direct socket");
  }
};
const moduleObject = { exports: {} };
const execute = new Function("require", "module", "exports", transformed);
execute((request) => {
  if (request === "@tarojs/taro") return { __esModule: true, default: taro };
  if (request === "../config/env") {
    return {
      CLOUDBASE_ENV_ID: "test-env",
      CLOUDBASE_SERVICE: "test-service",
      USE_CLOUDBASE_PRIVATE_ACCESS: true,
      WEBSOCKET_ORIGIN: "wss://must-not-be-used.invalid"
    };
  }
  throw new Error(`Unexpected require: ${request}`);
}, moduleObject, moduleObject.exports);

/** Verify that production HTTP and WebSocket calls stay on the private CloudBase boundary. */
async function main() {
  const { callCloudContainer, connectContainerSocket } = moduleObject.exports;
  const response = await callCloudContainer({
    path: "/api/health",
    method: "GET",
    header: { Authorization: "Bearer test-token" }
  });
  assert.deepEqual(response.data, { ok: true });
  assert.equal(calls.init.length, 1);
  assert.deepEqual(calls.init[0], { env: "test-env", traceUser: true });
  assert.equal(calls.http[0].config.env, "test-env");
  assert.equal(calls.http[0].header["X-WX-SERVICE"], "test-service");
  assert.equal(calls.http[0].header.Authorization, "Bearer test-token");

  const connected = await connectContainerSocket("/ws/game/ROOM01");
  assert.equal(connected, socketTask);
  assert.deepEqual(calls.socket[0], {
    service: "test-service",
    path: "/ws/game/ROOM01"
  });
  assert.equal(calls.init.length, 1, "CloudBase must initialize only once");
  console.log("CloudBase private HTTP/WebSocket transport: PASS");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
