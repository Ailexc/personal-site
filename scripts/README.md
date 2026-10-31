# 访问统计（ailexc.com）

主页的「访问统计」板块：总访问量 / 独立访客 / 今日 + 最近 30 天热力图。
数据完全自托管，不依赖任何第三方统计服务。

## 架构

```
访客 → Caddy (写 access-ailexc.log，JSON 行)
              ↓ cron 每 10 分钟
       collect-visits.py（增量解析、过滤、去重）
              ↓
        /home/admin/personal/visits.json
              ↓ fetch
       主页 assets/visits.js 渲染
```

## 组件

| 文件 | 职责 |
|---|---|
| `scripts/collect-visits.py` | 日志 → 统计 JSON（部署到 ali-light 的 `/home/admin/caddy-stats/`） |
| `public/assets/visits.js` | 前端渲染（数字滚动、热力图） |
| `public/maintenance/index.html` | 非开放时间维护页（与统计无关，但同属站点运维） |

## 部署

### 1. Caddy 开启访问日志

`ali-light:/home/admin/openclaw/caddy/Caddyfile` 的 `ailexc.com` 站点块内：

```caddy
ailexc.com {
    encode zstd gzip
    root * /srv/personal

    log {
        output file /data/access-ailexc.log {
            roll_size 50mb
            roll_keep 5
        }
        format json
    }
    ...
}
```

> ⚠️ **重要**：该容器的 bind mount 会失效（宿主机改文件后容器内仍是旧 inode）。
> 改完 Caddyfile 必须用 stdin 方式加载，不要依赖 `caddy reload` 读文件：
>
> ```bash
> docker exec -i caddy caddy validate --config - --adapter caddyfile < Caddyfile
> docker exec -i caddy caddy reload   --config - --adapter caddyfile < Caddyfile
> ```

### 2. 部署采集脚本

```bash
ssh ali-light
mkdir -p /home/admin/caddy-stats
# 从仓库同步
scp scripts/collect-visits.py ali-light:/home/admin/caddy-stats/
chmod +x /home/admin/caddy-stats/collect-visits.py
```

> 注意 ali-light 是 **Python 3.6.8**，脚本刻意避开 3.7+ 语法
> （无 `from __future__ import annotations`、无 `list[str]`、
> 无 `subprocess` 的 `capture_output`/`text` 参数）。

### 3. 配置定时任务

```bash
crontab -e
# 追加：
*/10 * * * * /usr/bin/python3 /home/admin/caddy-stats/collect-visits.py >> /home/admin/caddy-stats/collect.log 2>&1
```

### 4. 首次运行

```bash
cd /home/admin/caddy-stats && python3 collect-visits.py
```

产出 `/home/admin/personal/visits.json`，主页即可显示。

## 统计口径

| 项 | 规则 |
|---|---|
| 计入 | `GET`/`HEAD`、状态码 <400、URI 为 `/`、`/index.html`、`/resume*` |
| 排除 | 静态资源（`/assets/`、favicon、robots.txt）、`/visits.json` 自身 |
| 排除 | 已知爬虫 / 监控 / CLI 工具的 User-Agent（curl、wget、Googlebot、uptime 探针等） |
| PV | 每个符合条件的请求计 1 次 |
| UV | `sha256(ip + ua)` 前 16 位，按天去重；**不落盘原始 IP** |
| 时区 | 北京时间（`hardcoded +08:00`） |
| 保留 | 状态里留 120 天明细；输出只取最近 30 天 |

## 数据文件

| 路径 | 说明 |
|---|---|
| `/home/admin/caddy-stats/state.json` | 增量偏移 + 每日 PV/UV 哈希（**含访客指纹，勿公开**） |
| `/home/admin/personal/visits.json` | 对外输出（仅聚合数字，可直接访问） |
| `/home/admin/caddy-stats/collect.log` | cron 运行日志 |

## 维护

```bash
# 看最近运行情况
tail -5 /home/admin/caddy-stats/collect.log

# 全量重算（清状态，从现有日志重新聚合）
cd /home/admin/caddy-stats && python3 collect-visits.py --rebuild

# 彻底重置（清日志 + 清状态，历史归零）
cd /home/admin/caddy-stats && rm -f state.json && \
  docker exec caddy sh -c ': > /data/access-ailexc.log' && \
  python3 collect-visits.py
```

## 已知边界

- **延迟 ≤10 分钟**：cron 周期决定。要准实时需常驻服务，成本不成比例。
- **UV 是近似值**：同 IP + 同 UA 视为同一人；换浏览器/切网络会重复计。
- **不含你自己的访问**：未做 IP 排除，浏览时会虚高（量级很小，可接受）。
- **日志轮转**：`collect-visits.py` 检测到文件变小会自动把偏移归零，
  不会因轮转而重复统计或漏统计。
