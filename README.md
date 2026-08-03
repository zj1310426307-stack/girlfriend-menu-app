# 女朋友专属点菜小程序

前后端分离的手机端点菜应用，包含菜品管理、下单、我的点菜单、订单状态、管理端登录、爱心评价和历史统计。
项目同时包含一套微信小程序端，位于 `miniprogram/`，用于上传到微信小程序后台。

## 技术栈

- 前端：React + Vite + React Router + Axios
- 3D 小游戏：Three.js + React Three Fiber + Drei + Rapier Physics
- 后端：FastAPI + SQLAlchemy
- 数据库：生产环境 PostgreSQL，本地可继续使用 SQLite
- 微信小程序端：Taro + React

## 本地运行

需要 Python 3.10+ 和 Node.js 18+。

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload
```

`backend/.env.example` 默认使用本地 SQLite。管理端默认密码和邀请码写在本地 `.env` 中，可自行修改。

后端地址：`http://localhost:8000`  
接口文档：`http://localhost:8000/docs`

服务探针：

- 存活检查：`http://localhost:8000/api/health`
- 数据库就绪检查：`http://localhost:8000/api/ready`

### 2. 启动前端

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

前端默认通过 Vite 代理访问后端。也可以复制 `frontend/.env.example`，直接使用 `http://localhost:8000/api`。

- 点菜端：`http://localhost:5173/`
- 我的点菜单：`http://localhost:5173/my-orders`
- 管理端：`http://localhost:5173/admin`
- 管理端登录：`http://localhost:5173/admin/login`
- 大话骰游戏：`http://localhost:5173/games/dice`

## 大话骰 / 吹牛小游戏

点菜首页的“喝酒小游戏”入口会打开 `/games/dice`。游戏是独立懒加载模块，不会改变点菜、订单、评价或管理端接口。

- 支持 2～6 人单机模拟，默认是“我、玩家A、玩家B”。
- 每位玩家有 5 颗骰子，AI 只能依据自己的骰子和概率做出叫骰或开盅决定。
- 骰子由 Three.js 绘制真实六面立体结构，使用白色圆角磨砂材质、红蓝骰点、灯光、阴影和局部环境反射。
- 每局点数来自 Rapier 物理引擎中骰子的最终朝向。初速度、角速度、弹跳和相互碰撞只负责产生物理运动，不会先随机指定结果。
- 大话骰规则中，1 点在叫其他点数时作为万能点；直接叫 1 时只统计真正的 1。
- 页面针对手机触控和较低像素比做了性能限制，3D 资源只会在进入游戏页时加载。

`1.0.8` 版本进一步增加了 PBR 骰子与皮革骰盅材质、蓝色绒布桌面、HDR 酒吧环境光、碰撞粒子、镜头震动、横向摇骰手势和手机陀螺仪/加速度计控制。HDR 使用 Poly Haven 的 `Warm Bar` CC0 资源，保存在 `frontend/public/textures/warm_bar_1k.hdr`。

游戏默认使用 Web Audio 实时合成骰盅和骰子碰撞音效，不依赖外部音频文件。`frontend/public/sounds/` 仍保留 `dice_roll.mp3`、`dice_hit.mp3` 和 `cup_shake.mp3` 接口，方便后续替换为获得合法授权的录音。

本地测试：

1. 启动前后端，打开点菜首页。
2. 点击“喝酒小游戏”，确认进入 `/games/dice`。
3. 选择 2～6 人并点击“开始摇骰”，等待骰子碰撞并自然停稳。
4. 检查自己的 5 颗骰子结果，依次测试“叫骰”和“开”。
5. 开盅后确认能看到全桌骰子、实际数量和本局输家，再点击“再来一局”。

## 环境变量

### 后端必须配置

| 变量 | 用途 | 示例 |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 连接地址；本地不配置时使用 SQLite | `postgresql://user:password@host:5432/dbname` |
| `FRONTEND_URL` | 允许跨域访问的前端域名；多个域名用逗号分隔 | `https://menu.example.com` |
| `ADMIN_PASSWORD` | 管理端登录密码 | 使用强密码 |
| `ADMIN_INVITE_CODE` | 管理端登录邀请码；本地未配置时默认 `love2026` | 使用不易猜的邀请码 |
| `ADMIN_SECRET` | 管理 token 签名密钥 | 使用长随机字符串 |

可选变量：

- `UPLOAD_PROVIDER`：当前只支持 `local`，为后续 Cloudinary、七牛云、腾讯云 COS、阿里云 OSS 等对象存储预留。
- `PORT`：Render/Railway 会自动提供。

后端兼容平台可能提供的 `postgres://` 地址，并会自动转换为 SQLAlchemy 使用的 `postgresql://`。

### 前端必须配置

```text
VITE_API_BASE_URL=https://你的后端域名/api
```

Vite 环境变量会在构建时写入前端，因此修改后需要重新部署。

## 数据库说明

- 没有配置 `DATABASE_URL` 时，使用 `backend/girlfriend_menu.db`。
- 配置 PostgreSQL `DATABASE_URL` 后，SQLAlchemy 会连接 PostgreSQL。
- 后端启动时使用现有模型创建缺失表，不会主动删除表。
- `orders.customer_id` 会在旧数据库中缺失时自动补充，旧订单不会被删除。
- `dishes.is_active` 会在旧数据库中缺失时自动补充。管理端“删除菜品”实际执行安全下架，历史订单明细仍然保留。
- 本地 SQLite 文件不会自动上传到 PostgreSQL；首次线上部署会在新的 PostgreSQL 中创建相同表结构并写入测试菜品。

## 稳定性与自动测试

- 网页端和微信小程序的只读接口会对网络错误、`408`、`429`、`5xx` 自动重试两次，兼容 Render 免费服务冷启动。
- 请求最长等待 45 秒；失败页面提供手动重新加载按钮，图片加载失败会自动显示占位图。
- 订单详情只在页面可见且订单尚未结束时轮询，减少后台流量和手机耗电。
- 网页端包含全局错误恢复页和未知路由页面。
- 后端接口回归测试覆盖健康检查、下单、状态修改、评价、防重复评价和菜品安全下架。

本地运行后端测试：

```powershell
cd backend
pip install -r requirements-dev.txt
pytest -q
```

推送到 GitHub 后，`.github/workflows/ci.yml` 会自动执行后端测试、网页端生产构建和微信小程序构建。实现方式参考 [FastAPI 官方全栈模板](https://github.com/fastapi/full-stack-fastapi-template) 的测试与 CI 分层，以及 [Taro 官方项目](https://github.com/NervJS/taro) 的小程序生命周期处理思路。

## 上传到 GitHub

在 `girlfriend-menu-app` 目录执行：

```powershell
git init
git add .
git commit -m "Prepare girlfriend menu app for deployment"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

`.env`、SQLite 数据库、上传图片和依赖目录已被 `.gitignore` 排除，不会提交到 GitHub。

## 部署后端

### 方案 A：Render + Neon PostgreSQL（推荐）

Render 免费 PostgreSQL 会在创建 30 天后过期，因此长期使用时建议让 Render 只运行 FastAPI，把数据库放在 Neon：

1. 在 Neon 创建项目和 PostgreSQL 数据库。
2. 在 Neon 的 Connect 页面选择 pooled connection，复制以 `postgresql://` 开头并包含 `sslmode=require` 的连接地址。
3. 在 Render 创建 Web Service 并连接 GitHub 仓库。
4. Root Directory 填写 `backend`。
5. Build Command：

   ```text
   pip install -r requirements.txt
   ```

6. Start Command：

   ```text
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

7. 将 Neon 连接地址保存为 Render 的 `DATABASE_URL`，并配置 `FRONTEND_URL`、`ADMIN_PASSWORD`、`ADMIN_INVITE_CODE`、`ADMIN_SECRET`。
8. 部署完成后记录 `https://你的服务.onrender.com`。

`render.yaml` 将 `DATABASE_URL` 标记为手动配置，避免 Blueprint 再创建或绑定 30 天过期的 Render 免费数据库。仓库中的 `backend/Procfile` 已包含生产启动命令。Render 连接 GitHub 后，默认可在分支更新时自动重新部署。参考：[Render 部署与环境变量文档](https://render.com/docs/deploys)。

首次连接空的 Neon 数据库时，FastAPI 会自动创建 `dishes`、`orders`、`order_items`、`reviews` 表并写入测试菜品，不需要手动执行 SQL。旧 Render PostgreSQL 已过期时，只有在 Render 的恢复期内升级或导出后，旧订单和评价才可以迁移。

### 方案 B：Railway

1. 在 Railway 新建项目，选择 Deploy from GitHub repo。
2. 将后端服务的 Root Directory 设置为 `backend`。
3. 在同一个 Railway 项目中添加 PostgreSQL 服务。
4. 将 PostgreSQL 提供的 `DATABASE_URL` 配置到后端服务。
5. 配置 `FRONTEND_URL`、`ADMIN_PASSWORD`、`ADMIN_INVITE_CODE`、`ADMIN_SECRET`。
6. Start Command：

   ```text
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

7. 在后端服务 Networking 中选择 Generate Domain。

参考：[Railway FastAPI](https://docs.railway.com/guides/fastapi) 和 [Railway PostgreSQL](https://docs.railway.com/databases/postgresql)。

## 部署前端

先完成后端部署，取得后端公网域名。

### 方案 A：Vercel

1. 在 Vercel 导入 GitHub 仓库。
2. Root Directory 选择 `frontend`。
3. Framework Preset 选择 Vite。
4. Build Command 使用 `npm run build`，Output Directory 使用 `dist`。
5. 配置：

   ```text
   VITE_API_BASE_URL=https://你的后端域名/api
   ```

6. 部署完成后，把 Vercel 域名填回后端的 `FRONTEND_URL`，重新部署后端。

`frontend/vercel.json` 已配置 React Router 的 SPA rewrite，刷新 `/admin`、`/my-orders` 等页面不会返回 404。参考：[Vercel Vite SPA](https://vercel.com/docs/frameworks/frontend/vite)。

### 方案 B：Cloudflare Pages

1. 在 Cloudflare Workers & Pages 中选择 Import an existing Git repository。
2. Root Directory 选择 `frontend`。
3. Build Command 使用 `npm run build`。
4. Build Output Directory 使用 `dist`。
5. 配置：

   ```text
   VITE_API_BASE_URL=https://你的后端域名/api
   ```

6. 部署完成后，把 `pages.dev` 或自定义域名填回后端的 `FRONTEND_URL`。

Cloudflare Pages 在项目没有顶层 `404.html` 时会自动按 SPA 方式处理未知路径，因此 React Router 深层链接可以刷新。参考：[Cloudflare Pages React 部署](https://developers.cloudflare.com/pages/framework-guides/deploy-a-react-site/)。

## 线上图片说明

本地上传目前由 `backend/storage.py` 的存储接口保存到 `backend/uploads/`。Render、Railway 等平台的普通运行文件系统可能会在重启或重新部署后丢失这些文件。

第一版线上建议在菜品管理中填写稳定的公网 `image_url`，不会影响点菜核心功能。后续接入对象存储时，可在 `storage.py` 中新增 provider，并保持接口返回 `{ "image_url": "..." }` 不变。

## 我的点菜单

浏览器会在 `localStorage` 保存 `gf_customer_id`。提交订单时后端把它保存到 `orders.customer_id`，`/my-orders` 只查询当前浏览器的订单。

这不是账号系统。清空浏览器缓存、换浏览器或换设备后会生成新 ID，旧订单无法在“我的点菜单”自动找回，但管理端仍可查看全部订单。

## 线上功能验收

1. 打开前端公网网址并提交订单。
2. 关闭页面后重新打开，进入“我的点菜单”确认订单仍在。
3. 打开 `/admin`，使用 `ADMIN_PASSWORD` 和 `ADMIN_INVITE_CODE` 登录。
4. 把订单状态改为“已完成”。
5. 回到点菜端订单详情并提交爱心评价。
6. 再次进入详情，确认显示评价结果且不能重复评价。
7. 在管理端打开“点菜统计”，确认订单和菜品统计已更新。

## 自动部署

Render、Railway、Vercel 和 Cloudflare Pages 都可以连接 GitHub 仓库。完成首次配置后，推送到生产分支会自动触发构建和部署。前后端是两个独立服务，在云平台中分别将 Root Directory 设置为 `backend` 和 `frontend`。

## 微信小程序端

小程序端目录：`miniprogram/`。

当前小程序 AppID：

```text
wx08cb090781c3e679
```

小程序端复用线上后端接口：

```text
https://girlfriend-menu-api.onrender.com/api
```

第一版小程序只包含女朋友点菜端：

- 首次进入需要填写邀请码（当前默认：`love2026`）
- 首页菜品列表和分类筛选
- 菜品详情
- 点菜清单
- 我的点菜单
- 订单状态
- 已完成订单的爱心评价
- “3D 大话骰 · 吹牛”原生 WebGL 游戏模块
- “和女朋友实时对战”双人大话骰房间

管理端仍然使用网页：

```text
https://girlfriend-menu-web-zj13104.onrender.com/admin
```

### 构建小程序

```powershell
cd miniprogram
npm install
npm run build:weapp
```

构建完成后，用微信开发者工具打开 `miniprogram/` 目录。项目配置中的 `miniprogramRoot` 指向 `dist/`。

上传前可以运行完整冒烟测试。测试会清空开发者工具中的小程序存储、检查邀请码页、自动输入邀请码、确认线上菜品列表能够渲染，并验证原生 WebGL 桌面初始化、骰子碰撞状态、上滑开盅和 5 颗骰子结果：

```powershell
npm run test:smoke
```

该测试依赖本机微信开发者工具路径 `F:/浏览器/微信web开发者工具/cli.bat`。如果开发者工具安装在其他位置，请修改 `miniprogram/scripts/smoke-test.cjs` 中的 `CLI_PATH`。

### 吹牛 · 大话骰玩法

从首页点击“3D 大话骰 · 吹牛”进入 `pages/dice/index` 原生页面。小程序使用轻量的微信原生 WebGL Canvas 渲染，不通过 `web-view` 打开外部网页，也不再打包体积较大的 Three.js 兼容层，因此个人主体小程序和中低端手机都可以使用。

- 2～6 人单机模拟，每位玩家 5 颗骰子，并包含玩家 A、玩家 B 等 AI 对手。
- 5 颗白色圆角六面骰子在原生 WebGL 场景中翻滚、碰撞桌面和相互碰撞，点数从停止后的朝向计算。
- 包含 PBR 风格骰子、红蓝骰点、皮革骰盅、蓝色绒布桌面、灯光、阴影和镜头震动。
- `1.0.11` 使用程序化桌布纤维和皮革纹理、带凹槽层次的双色骰点、桌沿霓虹反射与空间微粒，并复用骰子几何体和材质以降低内存占用。
- 物理计算加入子步进、碰撞触感反馈和停稳后的落点分离，减少骰子穿透、重叠以及低帧率设备上的跳动。
- `1.0.12` 为摇动和停稳阶段增加统一的骰盅安全圆形边界；计算时预留骰子角点空间，骰子碰到内壁会向内反弹，最终落点也不会超出骰盅。
- `1.0.13` 曾尝试将游戏改为独立分包；由于部分真机无法打开，`1.0.14` 已恢复兼容性更高的主包普通页面。动态帧率、后台暂停和前台恢复功能继续保留。
- `1.0.16` 参考成熟开源骰子项目的做法，改为 120Hz 固定物理时间步、自动休眠和最大模拟时长双重停稳判定；静止桌面按需重绘，并在高像素密度手机上限制渲染倍率，降低耗电和发热。光照增加冷暖补光、距离雾化和更自然的骰子高光。
- 强碰撞时桌面外圈会出现短暂的蓝色光晕，与触感反馈同步，但不会增加图片或音频资源。
- 骰子停稳后需要在桌面上向上滑动打开骰盅。
- 上滑不方便时也可以轻触开盅提示打开骰盅。
- 支持叫骰、加码和开盅，并按照大话骰规则判断本局输赢。

单机 AI 模式的骰子结果只保留在游戏页面。双人实时模式只在当前房间中临时同步骰子结果，不写入数据库，也不影响菜品、订单和管理端统计。

### 和女朋友实时对战

小程序首页点击“和女朋友实时对战”进入 `pages/dice-online/index`：

1. 一方选择自己的房间名称并创建房间。
2. 复制 6 位房间码发给另一方。
3. 另一方选择名称并输入房间码加入。
4. 双方分别使用原生 3D 骰子桌摇出自己的 5 颗骰子；开盅前只能看到自己的结果。
5. 系统按回合实时同步叫骰、开盅和输赢，双方都点“再来一局”后开始下一局。

房间状态由 FastAPI WebSocket 服务维护，房间最多两人，并通过邀请码校验。第一版房间保存在单个后端进程的内存中；后端重启或重新部署后，需要重新创建房间。订单、菜品和评价仍保存在 PostgreSQL，不受影响。

### 实时订单

网页管理端 `/admin` 登录后会连接 `/ws/admin/orders`。女朋友提交订单、订单状态变化或完成评价时，管理端会立即刷新订单列表；WebSocket 暂时断开时仍保留原来的 10 秒轮询作为备用。

实现思路参考了以下优秀开源案例，但没有直接复制其场景代码：

- [3d-dice/dice-box](https://github.com/3d-dice/dice-box)：借鉴渲染、主题和物理状态分层，以及骰子停止后的休眠思路。
- [421-dice-game-app](https://github.com/delcourtfl/421-dice-game-app)：参考移动端 Three.js + 物理骰子游戏的交互节奏。
- [wechat-miniprogram/threejs-miniprogram](https://github.com/wechat-miniprogram/threejs-miniprogram)：参考微信 Canvas 获取与页面生命周期处理；正式代码继续使用更轻量的原生 WebGL，以避免旧 Three.js 兼容层增加真机包体和初始化压力。

### 上传微信小程序

1. 使用有该小程序开发权限的微信号登录微信开发者工具。
2. 打开 `girlfriend-menu-app/miniprogram`。
3. 确认 AppID 为 `wx08cb090781c3e679`。
4. 点击微信开发者工具右上角“上传”，版本号填写当前待发布版本（本地为 `1.0.17`）。
5. 到微信公众平台提交体验版或正式审核。

### 微信后台域名配置

微信公众平台需要在“开发管理 / 开发设置 / 服务器域名”中配置 request 合法域名：

```text
https://girlfriend-menu-api.onrender.com
```

实时双人骰子还需要在同一页面的 `socket 合法域名` 中填写：

```text
wss://girlfriend-menu-api.onrender.com
```

小程序骰子页面是原生 WebGL 页面，不再使用 `web-view`，所以无需配置“业务域名”。个人主体后台没有“业务域名”入口属于正常现象，不影响原生骰子与点菜功能。

如果微信后台不接受 Render 免费域名，建议给后端绑定自定义 HTTPS 域名，然后把 `miniprogram/src/api/index.js` 里的 `API_BASE_URL` 改成自定义域名对应的 `/api` 地址。

### 小程序历史订单说明

小程序会使用微信本地缓存保存 `gf_customer_id`，用于查询“我的点菜单”。这不是微信登录，也不获取手机号。清空小程序缓存或换设备后，历史订单可能无法自动找回；管理端仍可以查看所有订单。
