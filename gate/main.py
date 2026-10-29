"""简历下载门禁（L1：手机尾号 + 限流 + 短时签名 Cookie）。

部署：ali-light Docker，仅内网监听 8791，由 Caddy 反代 /resume* 路径。
配置（环境变量）：
  RESUME_CODE        期望的提取码（默认 0000，部署后请改）
  RESUME_CODE_SHA256 可选，优先于 RESUME_CODE（只存哈希更安全）
  RESUME_PDF         简历文件路径（默认 /data/resume.pdf）
  GATE_SECRET        签名密钥（默认从提取码派生，建议显式设置）
  MAX_ATTEMPTS       窗口内最大失败次数（默认 5）
  WINDOW_SECONDS     统计窗口（默认 900 秒）
  COOKIE_TTL         放行有效期（默认 1800 秒）
"""
import base64
import hashlib
import hmac
import os
import time
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

app = FastAPI(title="resume-gate", docs_url=None, redoc_url=None)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")

RESUME_CODE = os.environ.get("RESUME_CODE", "0000")
RESUME_CODE_SHA256 = os.environ.get("RESUME_CODE_SHA256", "").strip().lower()
RESUME_PDF = Path(os.environ.get("RESUME_PDF", "/data/resume.pdf"))
GATE_SECRET = os.environ.get("GATE_SECRET", f"gate::{RESUME_CODE}").encode()
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "5"))
WINDOW_SECONDS = int(os.environ.get("WINDOW_SECONDS", "900"))
COOKIE_TTL = int(os.environ.get("COOKIE_TTL", "1800"))

COOKIE_NAME = "resume_pass"
_failures: dict[str, list[float]] = {}

TEXT = {
    "zh": {
        "title": "简历下载",
        "subtitle": "为保护个人信息，请先完成一次简单验证。",
        "label": "请输入投递时登记的手机号后 4 位",
        "button": "验证并下载",
        "hint": "仅用于确认你是收到我简历的联系人；验证通过后可在 30 分钟内下载。",
        "error": "验证码不正确，请重试。",
        "locked": "尝试次数过多，请 15 分钟后再试。",
        "ok_title": "验证通过",
        "ok_sub": "点击下方按钮下载简历（链接 30 分钟内有效）。",
        "dl": "下载简历 PDF",
        "missing": "简历文件尚未上传，请稍后再试或直接邮件联系。",
    },
    "en": {
        "title": "Download CV",
        "subtitle": "A quick check keeps my contact details private.",
        "label": "Enter the last 4 digits of the phone number on my application",
        "button": "Verify and download",
        "hint": "This only confirms you received my CV. Access stays valid for 30 minutes.",
        "error": "Incorrect code. Please try again.",
        "locked": "Too many attempts. Please try again in 15 minutes.",
        "ok_title": "Verified",
        "ok_sub": "Use the button below to download the CV (valid for 30 minutes).",
        "dl": "Download CV (PDF)",
        "missing": "The CV file has not been uploaded yet. Please contact me by email.",
    },
}


def _t(lang: str) -> dict:
    return TEXT["en" if lang == "en" else "zh"]


def _render(lang: str, error: str = "") -> str:
    t = _t(lang)
    err_html = f'<div class="err">{error}</div>' if error else ""
    return (
        TEMPLATE.replace("{LANG}", "en" if lang == "en" else "zh")
        .replace("{TITLE}", t["title"])
        .replace("{SUBTITLE}", t["subtitle"])
        .replace("{LABEL}", t["label"])
        .replace("{BUTTON}", t["button"])
        .replace("{HINT}", t["hint"])
        .replace("{ERROR}", err_html)
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_locked(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _failures.get(ip, []) if now - t < WINDOW_SECONDS]
    _failures[ip] = hits
    return len(hits) >= MAX_ATTEMPTS


def _record_failure(ip: str) -> None:
    _failures.setdefault(ip, []).append(time.time())


def _expected_hash() -> str:
    if RESUME_CODE_SHA256:
        return RESUME_CODE_SHA256
    return hashlib.sha256(RESUME_CODE.encode()).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _token(expires: int) -> str:
    payload = f"ok:{expires}".encode()
    sig = hmac.new(GATE_SECRET, payload, hashlib.sha256).digest()
    # 两段分别 base64url 编码：分隔符 "." 不会与签名原始字节冲突
    return f"{_b64(payload)}.{_b64(sig)}"


def _valid_token(token: str) -> bool:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _unb64(payload_b64)
        sig = _unb64(sig_b64)
        expected = hmac.new(GATE_SECRET, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return False
        prefix, expires = payload.split(b":", 1)
        return prefix == b"ok" and int(expires) > time.time()
    except Exception:
        return False


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/resume", response_class=HTMLResponse)
def resume_page(request: Request, lang: str = "zh", err: str = ""):
    if request.cookies.get(COOKIE_NAME) and _valid_token(request.cookies[COOKIE_NAME]):
        return RedirectResponse("/resume/download", status_code=302)
    error = ""
    if err == "1":
        error = _t(lang)["error"]
    elif err == "2":
        error = _t(lang)["locked"]
    resp = HTMLResponse(_render(lang, error))
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@app.post("/resume/verify")
def resume_verify(request: Request, code: str = Form(""), lang: str = Form("zh")):
    ip = _client_ip(request)
    if _is_locked(ip):
        return RedirectResponse(f"/resume?lang={lang}&err=2", status_code=303)

    normalized = "".join(ch for ch in code if ch.isdigit())
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    if normalized and hmac.compare_digest(digest, _expected_hash()):
        expires = int(time.time()) + COOKIE_TTL
        resp = RedirectResponse("/resume/download", status_code=303)
        resp.set_cookie(
            COOKIE_NAME,
            _token(expires),
            max_age=COOKIE_TTL,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/resume",
        )
        return resp

    _record_failure(ip)
    return RedirectResponse(f"/resume?lang={lang}&err=1", status_code=303)


@app.get("/resume/download")
def resume_download(request: Request):
    token = request.cookies.get(COOKIE_NAME, "")
    if not _valid_token(token):
        return RedirectResponse("/resume", status_code=302)
    if not RESUME_PDF.exists():
        t = _t("zh")
        html = (
            '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
            '<body style="font-family:-apple-system,PingFang SC,sans-serif;display:grid;place-items:center;height:100vh;margin:0;background:#f6f7fb">'
            f'<div style="background:#fff;border:1px solid #e6e8ef;border-radius:16px;padding:28px 32px;max-width:420px">'
            f'<h2 style="margin:0 0 10px">{t["ok_title"]}</h2><p style="color:#6b7280">{t["missing"]}</p>'
            '<p><a href="/" style="color:#3155f5">← ailexc.com</a></p></div></body>'
        )
        return HTMLResponse(html, status_code=503)
    return FileResponse(
        RESUME_PDF,
        media_type="application/pdf",
        filename="ailexc-resume.pdf",
        headers={"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "private, no-store"},
    )
