# V2.8 数据备份与恢复

数据库备份包含订单、明细、评价、收藏、设备身份、情侣数据及实际存在的游戏核心表。备份目录已加入 `.gitignore`；备份可能包含私人备注、评价和身份标识，不得提交 GitHub 或发送到公共网盘。

## 迁移前备份

在 `girlfriend-menu-app` 根目录执行：

```powershell
python scripts/backup_database.py --database-url "$env:DATABASE_URL" --output-dir D:\secure-backups
```

PostgreSQL 需要系统可执行 `pg_dump`。脚本使用 custom format，另写一份 `.manifest.json`，记录 SHA-256 与关键表行数。生产连接串只通过命令行或后端 `.env` 提供，不写入仓库。

本地 SQLite：

```powershell
python scripts/backup_database.py --database-url "sqlite:///./girlfriend_menu.db"
```

脚本默认保留本机目录最近 14 天的同名前缀备份。正式环境还应把备份复制到加密、访问受控且与 Render/Neon 独立的位置。

## 恢复校验

SQLite 会恢复到系统临时目录，执行完整性检查并核对 manifest 中所有可用表的行数：

```powershell
python scripts/verify_backup.py backups\girlfriend-menu-YYYYMMDDTHHMMSSZ.sqlite3
```

PostgreSQL 必须使用隔离临时库，工具会拒绝不含 `restore_verify` 的目标地址：

```powershell
python scripts/verify_backup.py D:\secure-backups\girlfriend-menu-YYYYMMDDTHHMMSSZ.dump `
  --target-url "$env:RESTORE_VERIFY_DATABASE_URL"
```

校验依赖 `pg_restore`，会使用 `--clean --if-exists`，因此绝对不要把生产库地址作为 `--target-url`。

## 已执行演练

2026-08-10 已对本地 SQLite 执行“备份 → 临时库恢复 → `PRAGMA integrity_check` → 行数核对”，结果为 `status=verified`。实际核对包含 21 道菜、5 个订单以及本地存在的评价、情侣和游戏表。该演练证明脚本链路有效，但不替代 Neon 临时 PostgreSQL 库的正式发布前演练。

## 正式迁移顺序

1. 暂停管理端写操作。
2. 执行备份并保存 dump 与 manifest。
3. 在隔离临时库运行恢复核验。
4. 在后端目录执行 `alembic upgrade head`。
5. 检查 `/api/ready`、订单数量及最近订单。
6. 恢复管理端写操作。
