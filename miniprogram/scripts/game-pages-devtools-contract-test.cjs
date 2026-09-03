const assert = require("assert");
const fs = require("fs");
const path = require("path");

const acceptancePath = path.join(__dirname, "game-pages-devtools-acceptance.cjs");
const source = fs.readFileSync(acceptancePath, "utf8");
const smokePath = path.join(__dirname, "smoke-test.cjs");
const smokeSource = fs.readFileSync(smokePath, "utf8");

assert.match(source, /automator\.connect\(/, "acceptance must reuse an existing automation socket");
assert.match(source, /automator\.launch\(/, "acceptance must launch DevTools when no socket exists");
assert.match(source, /port:\s*HTTP_PORT/, "the automator websocket port must remain explicit");
assert.doesNotMatch(
  source,
  /WECHAT_DEVTOOLS_CLI_PORT|args:\s*\[\s*["']--port["']/,
  "do not override the IDE service port; the CLI discovers the enabled DevTools service"
);
assert.match(source, /snapshotSimulatorStorage/, "acceptance must snapshot simulator storage");
assert.match(source, /restoreSimulatorStorage/, "acceptance must restore simulator storage");
assert.match(source, /callWxMethod\("getStorageInfoSync"\)/, "acceptance must discover every original storage key");
assert.match(source, /callWxMethod\("clearStorageSync"\)/, "acceptance must remove smoke-only storage before restoration");
assert.match(source, /removeLegacySmokeSession/, "acceptance must migrate the exact sentinel leaked by older runs");
assert.match(source, /customerId !== LEGACY_SMOKE_SESSION\.customer_id[\s\S]*customerToken !== LEGACY_SMOKE_SESSION\.customer_token/);
assert.match(
  smokeSource,
  /process\.env\.WECHAT_SMOKE_CUSTOMER_INVITE_CODE/,
  "hosted smoke must receive the customer invite at runtime"
);
assert.doesNotMatch(
  smokeSource,
  /inviteInput\.input\(["'][^"']+["']\)/,
  "hosted smoke must not contain a hard-coded customer invite"
);
assert.match(
  smokeSource,
  /miniProgram\.callWxMethod\("getSystemInfoSync"\)/,
  "hosted smoke must reject an unresponsive existing automation socket"
);
assert.match(
  smokeSource,
  /DEVTOOLS_HOSTS = \["127\.0\.0\.2", "127\.0\.0\.1"\]/,
  "hosted smoke must bypass the Windows IDE HTTP binding before using the standard loopback"
);
assert.match(
  smokeSource,
  /assert\(!networkPolicyError, networkPolicyError\)/,
  "hosted smoke must fail explicitly when WeChat rejects the staging request domain"
);
assert.doesNotMatch(
  smokeSource,
  /if \(KEEP_OPEN \|\| !ownsDevtools\) \{[\s\S]{0,120}?return;/,
  "hosted smoke cleanup must not suppress an acceptance assertion"
);
assert.doesNotMatch(
  smokeSource,
  /WECHAT_DEVTOOLS_CLI_PORT|args:\s*\[\s*["']--port["']/,
  "hosted smoke must not override the DevTools IDE service port"
);

console.log("game pages DevTools launch contract PASS");
