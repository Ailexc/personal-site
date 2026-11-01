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
- **可排除自己**：`excludes.json` 里配 IP / 指纹，采集时跳过（见下方「排除自己」）。
- **日志轮转**：`collect-visits.py` 检测到文件变小会自动把偏移归零，
  不会因轮转而重复统计或漏统计。

---

## 项目点击统计

统计「有人从主页点开了哪个项目的哪个入口」。

### Caddy 侧

页面上的外链不再直连目标站，而是指向本站的 `/go/{project}/{kind}`，
Caddy 立刻 302 到真实地址 —— 这一跳会落进 `ailexc.com` 的 access log。

```caddy
handle /go/cumi/live {
    redir https://cumi.demo.ailexc.com 302
}
```

- `project`：`devops` / `cumi` / `review` / `anytra`
- `kind`：`live`（在线预览）/ `intro`（介绍页）/ `repo`（仓库）

> ⚠️ **必须 302，不能用 301**。301 会被浏览器永久缓存，
> 第二次点击根本不回服务器，统计直接归零。

### 口径

| 项 | 规则 |
|---|---|
| 计入 | `GET`/`HEAD`、状态码 <400、URI 形如 `/go/{p}/{k}` |
| 来源校验 | `Referer` 的 host 必须是 `ailexc.com`，否则视为分享出去的裸链接，**不计入** |
| PV | 每次点击 +1 |
| UV | `sha256(ip + ua)` 前 16 位，按天 + 项目 + 类型去重 |
| 上限 | 单日单项目单类型最多 5000 个 UV 哈希 |

**为什么校验 Referer**：`/go/cumi/live` 可以被右键复制走。分享到群里 20 个人打开，
会给这个项目凭空刷 20 次点击。判断来源域名能挡住这种污染——代价是隐私模式
浏览器会剥离 Referer，可能漏统计几个，但比被刷严重得多。

### 输出结构

```json
"clicks": {
  "since": "2026-11-01",
  "total_pv": 16,
  "total_uv": 4,
  "projects": [
    { "key": "devops", "pv": 7, "uv": 3,
      "kinds": { "live":  {"pv": 3, "uv": 3},
                 "intro": {"pv": 3, "uv": 3},
                 "repo":  {"pv": 1, "uv": 1} } }
  ]
}
```

`projects` 已按 UV 降序排好。前端只用原始数字，项目名与文案走 `i18n.js`。

> **UV 不可相加**：一个人点了「预览」又点「介绍页」，项目 UV 只算 1，
> 但两类各算 1，三类之和会大于项目 UV。所以堆叠条的段宽分母用
> 「三类 UV 之和」，而不是项目 UV。

## 排除自己

自己的访问会污染数据（开发时反复刷新尤其明显）。配置
`/home/admin/caddy-stats/excludes.json`：

```json
{
  "ips": ["1.2.3.4"],
  "hashes": ["135ca36f2f8d85d2"]
}
```

命中任一即跳过，不区分页面访问还是点击。

```bash
# 列出日志里的访客指纹（* 表示已排除）
python3 /home/admin/caddy-stats/collect-visits.py --list-visitors

# 改完 exclude 表要全量重算，才把历史数据一起剔除
python3 /home/admin/caddy-stats/collect-visits.py --rebuild
```

> IP 排除是整段生效：同一网络下的其他设备（手机、家人）也会一起被排除。
> 只想去掉某台设备就用 `hashes`，粒度更细。
