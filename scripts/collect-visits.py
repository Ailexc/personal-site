#!/usr/bin/env python3
"""聚合 Caddy 访问日志 → visits.json（个人主页访问统计）

设计要点
--------
- 数据源：Caddy access log（JSON 行），容器内 /data/access-ailexc.log
  容器以 root 写、宿主机 admin 读不了，因此通过 docker exec 增量读取。
- 增量：记录已消费的字节偏移；检测到文件变小（轮转/清空）时偏移归零。
- 隐私：不落盘原始 IP。独立访客按 sha256(ip + ua) 前 16 位去重，仅存哈希。
- 过滤：只统计页面请求（/、/index.html、/resume*），排除静态资源与爬虫/探针 UA。
- 输出：{站点根}/visits.json，供前端 fetch。

兼容性
------
    ali-light 上是 Python 3.6.8，因此不使用 3.7+ 语法
    （无 `from __future__ import annotations`、无 `list[str]`、
      无 subprocess 的 capture_output/text 参数）。

用法
----
    python3 collect.py                # 正常增量收集
    python3 collect.py --rebuild      # 忽略偏移，从头重算（state 重置）
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 配置 ────────────────────────────────────────────────────────────
CONTAINER = "caddy"
LOG_PATH = "/data/access-ailexc.log"
STATE_DIR = Path("/home/admin/caddy-stats")
STATE_FILE = STATE_DIR / "state.json"
OUTPUT_FILE = Path("/home/admin/personal/visits.json")

KEEP_DAYS = 120          # 状态里保留多少天的明细（输出只用最近 30 天）
MAX_HASHES_PER_DAY = 5000  # 单日 UV 哈希上限，防止异常流量撑爆状态文件
BJT = timezone(timedelta(hours=8))

# 爬虫 / 监控 / 工具类 UA 关键词（小写匹配）
BOT_KEYWORDS = (
    "bot", "spider", "crawl", "slurp", "archiver", "scraper",
    "googlebot", "bingbot", "baiduspider", "yandex", "duckduck",
    "semrush", "ahrefs", "mj12", "dotbot", "petalbot", "bytespider",
    "facebookexternalhit", "twitterbot", "linkedinbot", "telegrambot",
    "whatsapp", "slackbot", "discordbot",
    "uptime", "pingdom", "monitor", "statuscake", "freshping",
    "curl", "wget", "python-requests", "python-urllib", "go-http-client",
    "okhttp", "axios", "node-fetch", "libwww", "httpie", "powershell",
    "headlesschrome", "phantomjs", "lighthouse", "pagespeed",
    "zgrab", "masscan", "nmap", "censys", "shodan",
)


def run(cmd):
    """执行命令，返回 stdout 文本。"""
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         universal_newlines=True, timeout=60)
    return out.stdout


def log_size() -> int:
    """日志文件当前字节数；不存在返回 0。"""
    try:
        out = run(["docker", "exec", CONTAINER, "stat", "-c", "%s", LOG_PATH]).strip()
        return int(out) if out.isdigit() else 0
    except Exception:
        return 0


def read_incremental(offset: int) -> str:
    """读取从 offset 开始的新内容。"""
    # tail -c +N 表示从第 N 个字节开始（1-based）
    return run(["docker", "exec", CONTAINER, "tail", "-c", f"+{offset + 1}", LOG_PATH])


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"offset": 0, "days": {}}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(STATE_FILE)


def is_bot(ua: str) -> bool:
    u = (ua or "").strip().lower()
    if not u:
        return True  # 空 UA 一律视为非人类
    return any(k in u for k in BOT_KEYWORDS)


def is_page_view(uri: str) -> bool:
    """是否算一次页面访问（排除静态资源与内部数据文件）。"""
    if not uri:
        return False
    path = uri.split("?", 1)[0].split("#", 1)[0]
    if path in ("/", "/index.html"):
        return True
    # 简历下载/预览，说明是认真看的人
    if path == "/resume" or path.startswith("/resume/") or path.startswith("/resume."):
        return True
    return False


def visitor_hash(ip: str, ua: str) -> str:
    """访客指纹：只保留不可逆哈希，不落原始 IP。"""
    return hashlib.sha256(f"{ip}|{ua}".encode("utf-8", "ignore")).hexdigest()[:16]


def prune(state: dict) -> None:
    """裁掉过老的日期，并限制单日哈希数量。"""
    days = state.get("days", {})
    cutoff = (datetime.now(BJT) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for d in [k for k in days if k < cutoff]:
        del days[d]
    for d, rec in days.items():
        hashes = rec.get("h", [])
        if len(hashes) > MAX_HASHES_PER_DAY:
            rec["h"] = hashes[:MAX_HASHES_PER_DAY]


def build_output(state: dict) -> dict:
    """生成前端使用的 JSON（最近 30 天）。"""
    days_map = state.get("days", {})
    today = datetime.now(BJT).strftime("%Y-%m-%d")

    out_days = []
    for i in range(29, -1, -1):
        d = (datetime.now(BJT) - timedelta(days=i)).strftime("%Y-%m-%d")
        rec = days_map.get(d, {})
        out_days.append({
            "date": d,
            "pv": rec.get("pv", 0),
            "uv": len(rec.get("h", [])),
        })

    total_pv = sum(v.get("pv", 0) for v in days_map.values())
    total_uv = sum(len(v.get("h", [])) for v in days_map.values())
    today_rec = days_map.get(today, {})

    all_dates = sorted(days_map.keys())
    return {
        "generated_at": datetime.now(BJT).isoformat(timespec="seconds"),
        "since": all_dates[0] if all_dates else today,
        "total_pv": total_pv,
        "total_uv": total_uv,
        "today_pv": today_rec.get("pv", 0),
        "today_uv": len(today_rec.get("h", [])),
        "days": out_days,
    }


def main() -> int:
    rebuild = "--rebuild" in sys.argv
    state = load_state() if not rebuild else {"offset": 0, "days": {}}

    size = log_size()
    if size == 0:
        # 日志为空（刚开启或刚清空）：仍要产出一份空结构，
        # 否则前端 fetch 失败会隐藏整个板块
        out = build_output(state)
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUTPUT_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(OUTPUT_FILE)
        try:
            os.chmod(OUTPUT_FILE, 0o644)
        except OSError:
            pass
        print("日志为空，已产出空统计")
        return 0

    offset = int(state.get("offset", 0))
    if rebuild or size < offset:
        # 重建，或日志被轮转/清空
        offset = 0

    if size <= offset:
        print(f"无新增数据（offset={offset}, size={size}）")
        # 仍刷新一次输出，保证 generated_at 最新
        OUTPUT_FILE.write_text(
            json.dumps(build_output(state), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return 0

    chunk = read_incremental(offset)
    if not chunk:
        print("读取为空，跳过")
        return 0

    days = state.setdefault("days", {})
    added = 0
    skipped = 0

    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue

        # 只统计真正的页面响应
        status = rec.get("status")
        if not isinstance(status, int) or status >= 400:
            continue
        req = rec.get("request") or {}
        if (req.get("method") or "").upper() not in ("GET", "HEAD"):
            continue
        if not is_page_view(req.get("uri") or ""):
            continue

        headers = req.get("headers") or {}
        ua_list = headers.get("User-Agent") or [""]
        ua = ua_list[0] if isinstance(ua_list, list) and ua_list else ""
        if is_bot(ua):
            continue

        ts = rec.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        day = datetime.fromtimestamp(ts, BJT).strftime("%Y-%m-%d")

        ip = req.get("client_ip") or req.get("remote_ip") or ""
        h = visitor_hash(ip, ua)

        d = days.setdefault(day, {"pv": 0, "h": []})
        d["pv"] = d.get("pv", 0) + 1
        if h not in d["h"] and len(d["h"]) < MAX_HASHES_PER_DAY:
            d["h"].append(h)
        added += 1

    state["offset"] = size
    prune(state)
    save_state(state)

    out = build_output(state)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUTPUT_FILE)
    try:
        os.chmod(OUTPUT_FILE, 0o644)
    except OSError:
        pass

    print(f"新增页面访问 {added} 条（跳过异常行 {skipped}），"
          f"总 PV={out['total_pv']} UV={out['total_uv']}，今日 PV={out['today_pv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
