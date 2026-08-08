import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const outputDirectory = resolve("dist");
rmSync(outputDirectory, { recursive: true, force: true });
mkdirSync(outputDirectory, { recursive: true });

writeFileSync(resolve(outputDirectory, "index.html"), `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="robots" content="noindex,nofollow" />
    <title>网页端已停用</title>
    <style>
      * { box-sizing: border-box; }
      body { min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 28px; color: #5c4540; background: radial-gradient(circle at 20% 10%, #ffe8ed, transparent 35%), #fff9f6; font-family: system-ui, -apple-system, "PingFang SC", sans-serif; }
      main { width: min(100%, 430px); padding: 42px 30px; border: 1px solid #efdcd6; border-radius: 28px; background: rgba(255,255,255,.95); box-shadow: 0 22px 60px rgba(97,63,55,.12); text-align: center; }
      i { width: 72px; height: 72px; margin: 0 auto 20px; display: grid; place-items: center; border-radius: 24px; color: white; background: linear-gradient(135deg, #e9788f, #c9506a); font-size: 34px; font-style: normal; }
      h1 { margin: 0; font-size: 28px; }
      p { margin: 14px 0 0; color: #9a7a72; font-size: 16px; line-height: 1.75; }
      strong { color: #cb526a; }
    </style>
  </head>
  <body>
    <main>
      <i>♥</i>
      <h1>网页点菜端已停用</h1>
      <p>为了获得完整体验，请在微信中打开<br /><strong>“女朋友专属点菜小程序”</strong>。</p>
    </main>
  </body>
</html>`, "utf8");
