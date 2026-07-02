# 女朋友专属点菜小程序

前后端分离的手机端点菜应用，包含菜品管理、下单、我的点菜单、订单状态、管理端登录、爱心评价和历史统计。

## 技术栈

- 前端：React + Vite + React Router + Axios
- 后端：FastAPI + SQLAlchemy
- 数据库：生产环境 PostgreSQL，本地可继续使用 SQLite

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

`backend/.env.example` 默认使用本地 SQLite。管理端默认密码写在本地 `.env` 中，可自行修改。

后端地址：`http://localhost:8000`  
接口文档：`http://localhost:8000/docs`

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

## 环境变量

### 后端必须配置

| 变量 | 用途 | 示例 |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 连接地址；本地不配置时使用 SQLite | `postgresql://user:password@host:5432/dbname` |
| `FRONTEND_URL` | 允许跨域访问的前端域名；多个域名用逗号分隔 | `https://menu.example.com` |
| `ADMIN_PASSWORD` | 管理端登录密码 | 使用强密码 |
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
- 本地 SQLite 文件不会自动上传到 PostgreSQL；首次线上部署会在新的 PostgreSQL 中创建相同表结构并写入测试菜品。

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

### 方案 A：Render

1. 在 Render 创建 PostgreSQL 数据库，复制其内部连接地址。
2. 创建 Web Service 并连接 GitHub 仓库。
3. Root Directory 填写 `backend`。
4. Build Command：

   ```text
   pip install -r requirements.txt
   ```

5. Start Command：

   ```text
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

6. 配置 `DATABASE_URL`、`FRONTEND_URL`、`ADMIN_PASSWORD`、`ADMIN_SECRET`。
7. 部署完成后记录 `https://你的服务.onrender.com`。

仓库中的 `backend/Procfile` 已包含生产启动命令。Render 连接 GitHub 后，默认可在分支更新时自动重新部署。参考：[Render 部署与环境变量文档](https://render.com/docs/deploys)。

### 方案 B：Railway

1. 在 Railway 新建项目，选择 Deploy from GitHub repo。
2. 将后端服务的 Root Directory 设置为 `backend`。
3. 在同一个 Railway 项目中添加 PostgreSQL 服务。
4. 将 PostgreSQL 提供的 `DATABASE_URL` 配置到后端服务。
5. 配置 `FRONTEND_URL`、`ADMIN_PASSWORD`、`ADMIN_SECRET`。
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
3. 打开 `/admin`，使用 `ADMIN_PASSWORD` 登录。
4. 把订单状态改为“已完成”。
5. 回到点菜端订单详情并提交爱心评价。
6. 再次进入详情，确认显示评价结果且不能重复评价。
7. 在管理端打开“点菜统计”，确认订单和菜品统计已更新。

## 自动部署

Render、Railway、Vercel 和 Cloudflare Pages 都可以连接 GitHub 仓库。完成首次配置后，推送到生产分支会自动触发构建和部署。前后端是两个独立服务，在云平台中分别将 Root Directory 设置为 `backend` 和 `frontend`。
