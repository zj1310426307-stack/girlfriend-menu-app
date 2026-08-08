# 女朋友专属点菜小程序

这是一个只通过微信小程序访问的情侣私厨点菜系统。React/Vite 网页应用已在 `1.0.19` 中移除；用户端和管理端都位于同一个微信小程序，FastAPI 后端继续负责菜单、订单、评价、统计和实时对战数据，生产数据库使用 Neon PostgreSQL。`frontend/` 仅保留一张临时停用提示页，用于在 Render 静态服务彻底删除前阻止旧网页应用继续使用，不包含任何点菜功能。

## 当前功能

女朋友端：

- 邀请码进入小程序
- 菜品列表、分类筛选和菜品详情
- 点菜清单、备注、希望用餐时间和提交订单
- “我的点菜单”、订单状态和爱心评价
- 自定义转盘
- 单机 3D 大话骰、AI 对局和双人实时房间

小程序管理端：

- 首页点击“小厨房管理”进入
- 管理密码登录和退出登录
- 实时查看全部订单、备注和希望用餐时间
- 修改订单状态：待接单、已接单、制作中、已完成、暂时做不了
- 新增、编辑、下架菜品
- 从相册/相机上传菜品图片，或手动填写图片链接
- 总订单数、已完成数、最常点 Top 5、最近 10 次点菜
- 平均评分、评分最高的菜品和评价记录

当前小程序开发版本：`1.0.19`。

## 项目结构

```text
girlfriend-menu-app/
├── backend/                  # FastAPI、SQLAlchemy、PostgreSQL/SQLite
├── frontend/                 # 旧网址停用提示（不是应用，删除 Render 静态服务后可移除）
├── miniprogram/              # Taro React 微信小程序（唯一界面）
│   ├── config/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   └── utils/
│   ├── project.config.json
│   └── package.json
├── render.yaml               # 只部署 FastAPI 服务
└── README.md
```

## 本地运行

### 1. 启动后端

Windows CMD：

```bat
cd /d D:\my-project\girlfriend-menu-app\backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

如果 `8000` 端口出现 `WinError 10013`，可换用：

```bat
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

没有配置 `DATABASE_URL` 时，后端默认使用 `backend/girlfriend_menu.db`。启动后可访问 `http://127.0.0.1:8000/docs` 检查 API。

### 2. 构建微信小程序

```bat
cd /d D:\my-project\girlfriend-menu-app\miniprogram
npm install
npm run build:weapp
```

微信开发者工具导入目录：

```text
D:\my-project\girlfriend-menu-app\miniprogram
```

项目 AppID 已配置为：

```text
wx08cb090781c3e679
```

`project.config.json` 的 `miniprogramRoot` 指向 `dist/`。修改代码时可以运行 `npm run dev:weapp` 持续编译。

> 小程序当前 API 地址在 `miniprogram/src/api/index.js` 中配置为生产后端。若要完全离线联调，需要把它临时改为本机可被手机访问的 HTTPS 地址；微信真机不能直接请求电脑的 `localhost`。

## 生产部署

### 后端：Render + Neon PostgreSQL

Render 只部署 `backend/`，启动命令：

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

生产环境必须配置：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | Neon PostgreSQL 连接串 |
| `ADMIN_PASSWORD` | 小程序管理端密码 |
| `ADMIN_INVITE_CODE` | 管理接口邀请码，应与小程序邀请码保持一致 |
| `ADMIN_SECRET` | 足够长的随机管理令牌密钥 |

可选变量：

| 变量 | 说明 |
| --- | --- |
| `UPLOAD_PROVIDER` | 当前仅支持 `local` |
| `FRONTEND_URL` | 仅为未来获准的浏览器客户端预留；微信小程序不需要配置 |

部署后健康检查：

```text
https://girlfriend-menu-api.onrender.com/api/health
```

### 微信公众平台合法域名

在“开发管理 → 开发设置 → 服务器域名”配置：

| 类型 | 域名 |
| --- | --- |
| request 合法域名 | `https://girlfriend-menu-api.onrender.com` |
| socket 合法域名 | `wss://girlfriend-menu-api.onrender.com` |
| uploadFile 合法域名 | `https://girlfriend-menu-api.onrender.com` |
| downloadFile 合法域名 | `https://girlfriend-menu-api.onrender.com` |

不要在域名末尾添加 `/api`、路径、端口或分号。

### 构建、预览和上传

1. 在 `miniprogram/` 执行 `npm run build:weapp`。
2. 微信开发者工具打开 `miniprogram/`。
3. 点击“编译”，确认首页、点菜和管理端均可打开。
4. 点击“预览”，使用真实手机完成一次完整测试。
5. 点击“上传”，版本号填写 `1.0.19`。
6. 微信公众平台进入“版本管理”，将开发版本设为体验版；确认无误后提交审核。

## 完整测试流程

1. 输入邀请码进入首页，确认菜单正常显示。
2. 加入菜品、填写备注和希望用餐时间，提交订单。
3. 关闭后重新打开小程序，从“我的点菜单”找到刚才的订单。
4. 首页进入“小厨房管理”，输入管理密码。
5. 在“订单”页确认能实时看到订单，并把状态改为“已完成”。
6. 回到订单详情提交爱心评价，再次打开时应只显示评价结果。
7. 在“统计”页确认总订单、Top 5、评分和最近记录正确。
8. 在“菜品”页新增一条测试菜品、编辑后再下架，确认点菜页同步更新。
9. 测试转盘、单机骰子和双人房间。

## 数据与边界说明

- “我的点菜单”使用微信本地存储中的 `gf_customer_id` 识别当前设备。清空小程序缓存后，旧订单可能无法自动找回，管理端仍能看到全部订单。
- 管理登录令牌保存在微信本地存储中；没有复杂用户系统或注册功能。
- SQLite 旧库启动时会自动补充缺失字段和索引，不会重建或删除旧数据。
- Render 本地磁盘是临时存储。当前图片上传接口可用，但服务重启或重新部署后，本地上传文件可能丢失；正式长期使用建议填写稳定的 HTTPS 图片链接，或后续接入 Cloudinary、腾讯云 COS、阿里云 OSS 等对象存储。
- 后端和 Neon 数据库不能删除：它们是小程序保存菜品、订单、评价、统计和实时房间的服务，不属于已取消的网页端。

## 常用命令

```bat
cd /d D:\my-project\girlfriend-menu-app\backend
.venv\Scripts\python.exe -m pytest -q

cd /d D:\my-project\girlfriend-menu-app\miniprogram
npm run build:weapp
```
