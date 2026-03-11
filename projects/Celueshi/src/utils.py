from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WECHAT_DROP_QUERY_KEYS = {
    "scene",
    "clicktime",
    "enterid",
    "chksm",
    "mpshare",
    "srcid",
    "sharer_shareinfo",
    "sharer_shareinfo_first",
    "share_from",
    "from",
    "subscene",
    "wx_header",
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_within_root(path: Path, root: Path | None = None) -> Path:
    root = (root or PROJECT_ROOT).resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path escapes project root: {resolved}")
    return resolved


def resolve_project_path(raw_path: str | Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return ensure_within_root(candidate)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def relative_to_root(path: Path) -> str:
    return ensure_within_root(path).relative_to(PROJECT_ROOT).as_posix()


def normalize_text(value: str) -> str:
    return " ".join((value or "").replace("\u00a0", " ").split())


def normalize_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url or "", url)
    parsed = urlparse(absolute)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    normalized = parsed._replace(
        scheme=(parsed.scheme or "https").lower(),
        netloc=parsed.netloc.lower(),
        path=(parsed.path.rstrip("/") or "/"),
        params="",
        query=urlencode(filtered_query, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def normalize_wechat_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url or "", url)
    parsed = urlparse(absolute)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in WECHAT_DROP_QUERY_KEYS and not key.lower().startswith("utm_")
    ]
    normalized = parsed._replace(
        scheme="https",
        netloc="mp.weixin.qq.com",
        path=parsed.path or "/s",
        params="",
        query=urlencode(query, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def sha1_url(url: str) -> str:
    return hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()
