#!/usr/bin/env python3
"""聚合 Caddy 访问日志 → visits.json（个人主页访问统计）

设计要点
--------
- 数据源：Caddy access log（JSON 行），容器内 /data/access-ailexc.log
  容器以 root 写、宿主机 admin 读不了，因此通过 docker exec 增量读取。
- 增量：记录已消费的字节偏移；检测到文件变小（轮转/清空）时偏移归零。
- 隐私：不落盘原始 IP。独立访客按 sha256(ip + ua) 前 16 位去重，仅存哈希。
- 两类事件分开统计，互不污染：
    · 页面访问 / · /index.html · /resume*   → total_pv / days[].pv
    · 外链点击 /go/{project}/{kind}          → clicks.projects
  点击若混进页面访问，总 PV 会虚高（点一次项目凭空多一次浏览）。
- 点击只认真实主页来源：Referer 的 host 必须是 ailexc.com。
  裸链接被分享出去后别人打开也会跳转，但 Referer 为空或外部，不计入主数据。
- 排除自己：excludes.json 里存 IP 与指纹，采集时跳过。
- 输出：{站点根}/visits.json，供前端 fetch。

兼容性
------
    ali-light 上是 Python 3.6.8，因此不使用 3.7+ 语法
    （无 `from __future__ import annotations`、无 `list[str]`、
      无 subprocess 的 capture_output/text 参数）。

用法
----
    python3 collect-visits.py                 # 正常增量收集
    python3 collect-visits.py --rebuild       # 忽略偏移，从头重算
    python3 collect-visits.py --list-visitors # 列出访客指纹（维护排除表）
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from urllib.parse import urlparse
except ImportError:  # pragma: no cover
    from urlparse import urlparse

# ── 配置 ────────────────────────────────────────────────────────────
CONTAINER = "caddy"
LOG_PATH = "/data/access-ailexc.log"
STATE_DIR = Path("/home/admin/caddy-stats")
STATE_FILE = STATE_DIR / "state.json"
EXCLUDE_FILE = STATE_DIR / "excludes.json"
OUTPUT_FILE = Path("/home/admin/personal/visits.json")

SITE_HOST = "ailexc.com"
KEEP_DAYS = 120          # 状态里保留多少天的明细（输出只用最近 30 天）
MAX_HASHES_PER_DAY = 5000  # 单日 UV 哈希上限，防止异常流量撑爆状态文件
BJT = timezone(timedelta(hours=8))

# 项目外链路径：/go/{project}/{kind}
GO_PREFIX = "/go/"
PROJECT_KEYS = ("devops", "cumi", "review", "anytra")
CLICK_KINDS = ("live", "intro", "repo")

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
    # 扫描器常见伪装（2026-11 实测：站上 36 个"访客"里多数是这些）
    "redirectchecker", "scanner", "probe",
    "iphone os 13_2_3",   # 广为人知的扫描器假 UA
    "compatible; ",        # 大量采集器使用 "compatible; <bot>"
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


def empty_state() -> dict:
    return {"offset": 0, "days": {}, "clicks": {}}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            st.setdefault("offset", 0)
            st.setdefault("days", {})
            st.setdefault("clicks", {})
            return st
        except (json.JSONDecodeError, OSError):
            pass
    return empty_state()


def save_json(path: Path, data: dict, mode=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    if mode is not None:
        try:
            os.chmod(path, mode)
        except OSError:
            pass


def save_state(state: dict) -> None:
    save_json(STATE_FILE, state)


def load_excludes():
    """返回 (排除 IP 集合, 排除指纹集合)。文件缺失时视为空。"""
    if EXCLUDE_FILE.exists():
        try:
            d = json.loads(EXCLUDE_FILE.read_text(encoding="utf-8"))
            return set(d.get("ips") or []), set(d.get("hashes") or [])
        except (json.JSONDecodeError, OSError):
            pass
    return set(), set()


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


def parse_go_click(uri: str):
    """ /go/{project}/{kind} → "project|kind"，非点击路径返回 None。"""
    if not uri:
        return None
    path = uri.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not path.startswith(GO_PREFIX):
        return None
    parts = path[len(GO_PREFIX):].split("/")
    if len(parts) != 2:
        return None
    project, kind = parts[0], parts[1]
    if project not in PROJECT_KEYS or kind not in CLICK_KINDS:
        return None
    return project + "|" + kind


def is_from_site(referer: str) -> bool:
    """Referer 是否来自本站（区分真实点击 vs 分享出去的裸链接）。"""
    if not referer:
        return False
    try:
        host = (urlparse(referer).hostname or "").lower()
    except ValueError:
        return False
    return host == SITE_HOST or host == "www." + SITE_HOST


def visitor_hash(ip: str, ua: str) -> str:
    """访客指纹：只保留不可逆哈希，不落原始 IP。"""
    return hashlib.sha256(f"{ip}|{ua}".encode("utf-8", "ignore")).hexdigest()[:16]


def prune(state: dict) -> None:
    """裁掉过老的日期，并限制单日哈希数量。"""
    cutoff = (datetime.now(BJT) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")

    days = state.get("days", {})
    for d in [k for k in days if k < cutoff]:
        del days[d]
    for d, rec in days.items():
        hashes = rec.get("h", [])
        if len(hashes) > MAX_HASHES_PER_DAY:
            rec["h"] = hashes[:MAX_HASHES_PER_DAY]

    clicks = state.get("clicks", {})
    for key in [k for k in clicks if k.split("|", 1)[0] < cutoff]:
        del clicks[key]
    for rec in clicks.values():
        hashes = rec.get("h", [])
        if len(hashes) > MAX_HASHES_PER_DAY:
            rec["h"] = hashes[:MAX_HASHES_PER_DAY]


def build_clicks(state: dict) -> dict:
    """把扁平的 "date|project|kind" 记录聚合成前端的项目视图。"""
    raw = state.get("clicks", {})
    dates = sorted({k.split("|", 1)[0] for k in raw})

    bucket = {}
    for key, rec in raw.items():
        parts = key.split("|")
        if len(parts) != 3:
            continue
        _day, project, kind = parts
        p = bucket.setdefault(project, {
            "pv": 0, "hashes": set(),
            "kinds": {k: {"pv": 0, "hashes": set()} for k in CLICK_KINDS},
        })
        pv = rec.get("pv", 0)
        hs = rec.get("h", [])
        p["pv"] += pv
        p["hashes"].update(hs)
        k = p["kinds"][kind]
        k["pv"] += pv
        k["hashes"].update(hs)

    projects = []
    all_hashes = set()
    for key in PROJECT_KEYS:
        p = bucket.get(key)
        if not p:
            continue
        all_hashes.update(p["hashes"])
        projects.append({
            "key": key,
            "pv": p["pv"],
            "uv": len(p["hashes"]),
            "kinds": {
                kind: {"pv": p["kinds"][kind]["pv"],
                       "uv": len(p["kinds"][kind]["hashes"])}
                for kind in CLICK_KINDS
            },
        })

    # 合计按 UV 降序，并列时看 PV
    projects.sort(key=lambda x: (x["uv"], x["pv"]), reverse=True)

    return {
        "since": dates[0] if dates else "",
        "total_pv": sum(p["pv"] for p in projects),
        "total_uv": len(all_hashes),
        "projects": projects,
    }


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
        "clicks": build_clicks(state),
    }


def write_output(state: dict) -> None:
    save_json(OUTPUT_FILE, build_output(state), mode=0o644)


def list_visitors() -> int:
    """列出日志中的访客指纹，用于维护 excludes.json。"""
    if log_size() == 0:
        print("日志为空")
        return 0
    chunk = read_incremental(0)

    from collections import Counter
    counter = Counter()
    meta = {}
    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        req = rec.get("request") or {}
        if req.get("host") not in (SITE_HOST, SITE_HOST + ":443"):
            continue
        if (req.get("method") or "").upper() not in ("GET", "HEAD"):
            continue
        uri = req.get("uri") or ""
        if not (is_page_view(uri) or parse_go_click(uri)):
            continue
        ua = (req.get("headers", {}).get("User-Agent") or [""])[0]
        ip = req.get("client_ip") or req.get("remote_ip") or ""
        h = visitor_hash(ip, ua)
        counter[h] += 1
        meta[h] = (ip, ua)

    ex_ips, ex_hashes = load_excludes()
    print("共 %d 个指纹（* 已排除，[bot] 已被过滤）：\n" % len(counter))
    for h, n in counter.most_common(40):
        ip, ua = meta[h]
        mark = "*" if (h in ex_hashes or ip in ex_ips) else " "
        bot = " [bot]" if is_bot(ua) else ""
        print("%s %s %3d 次  %-16s %s%s" % (mark, h, n, ip, ua[:64], bot))
    print("\n排除表：%s" % EXCLUDE_FILE)
    print('格式：{"ips": ["1.2.3.4"], "hashes": ["abc123..."]}')
    return 0


def main() -> int:
    if "--list-visitors" in sys.argv:
        return list_visitors()

    rebuild = "--rebuild" in sys.argv
    state = empty_state() if rebuild else load_state()
    ex_ips, ex_hashes = load_excludes()

    size = log_size()
    if size == 0:
        # 日志为空（刚开启或刚清空）：仍要产出一份空结构，
        # 否则前端 fetch 失败会隐藏整个板块
        write_output(state)
        print("日志为空，已产出空统计")
        return 0

    offset = int(state.get("offset", 0))
    if rebuild or size < offset:
        # 重建，或日志被轮转/清空
        offset = 0

    if size <= offset:
        print(f"无新增数据（offset={offset}, size={size}）")
        write_output(state)  # 仍刷新一次，保证 generated_at 最新
        return 0

    chunk = read_incremental(offset)
    if not chunk:
        print("读取为空，跳过")
        return 0

    days = state.setdefault("days", {})
    clicks = state.setdefault("clicks", {})
    added = 0      # 页面访问
    clicked = 0    # 有效点击（来自本站）
    shared = 0     # 分享链接（Referer 非本站），不计入
    excluded = 0   # 命中排除表
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

        # 只统计真正的成功响应
        status = rec.get("status")
        if not isinstance(status, int) or status >= 400:
            continue
        req = rec.get("request") or {}
        if (req.get("method") or "").upper() not in ("GET", "HEAD"):
            continue
        if req.get("host") not in (SITE_HOST, SITE_HOST + ":443"):
            continue

        uri = req.get("uri") or ""
        click_key = parse_go_click(uri)
        if not click_key and not is_page_view(uri):
            continue

        headers = req.get("headers") or {}
        ua_list = headers.get("User-Agent") or [""]
        ua = ua_list[0] if isinstance(ua_list, list) and ua_list else ""
        if is_bot(ua):
            continue

        ts = rec.get("ts")
        if not isinstance(ts, (int, float)):
            continue

        ip = req.get("client_ip") or req.get("remote_ip") or ""
        h = visitor_hash(ip, ua)
        # 排除自己（IP 或指纹命中即跳过）
        if ip in ex_ips or h in ex_hashes:
            excluded += 1
            continue

        day = datetime.fromtimestamp(ts, BJT).strftime("%Y-%m-%d")

        if click_key:
            # 分享出去的裸链接：Referer 为空或非本站 → 不计入主数据
            ref_list = headers.get("Referer") or [""]
            referer = ref_list[0] if isinstance(ref_list, list) and ref_list else ""
            if not is_from_site(referer):
                shared += 1
                continue
            d = clicks.setdefault(day + "|" + click_key, {"pv": 0, "h": []})
            d["pv"] = d.get("pv", 0) + 1
            if h not in d["h"] and len(d["h"]) < MAX_HASHES_PER_DAY:
                d["h"].append(h)
            clicked += 1
        else:
            d = days.setdefault(day, {"pv": 0, "h": []})
            d["pv"] = d.get("pv", 0) + 1
            if h not in d["h"] and len(d["h"]) < MAX_HASHES_PER_DAY:
                d["h"].append(h)
            added += 1

    state["offset"] = size
    prune(state)
    save_state(state)
    write_output(state)

    out = build_output(state)
    print("新增页面访问 %d 条、项目点击 %d 次"
          "（分享来源跳过 %d，排除自己 %d，异常行 %d）"
          % (added, clicked, shared, excluded, skipped))
    print("累计：PV=%d UV=%d，今日 PV=%d；点击合计 %d 次 / %d 人"
          % (out["total_pv"], out["total_uv"], out["today_pv"],
             out["clicks"]["total_pv"], out["clicks"]["total_uv"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
