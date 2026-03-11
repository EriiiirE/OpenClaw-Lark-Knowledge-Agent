from __future__ import annotations

import re
from pathlib import Path

from models import SectionRecord

SOURCE_LINE_RE = re.compile(r"^>\s*来源[:：]\s*(\S+)\s*$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
TIMESTAMP_LINE_RE = re.compile(r"^\d{1,2}分\d{2}秒$")
NARRATOR_LINE_RE = re.compile(r"^[｜|].*音频转述师.*[｜|]$")
SOURCE_PROMO_RE = re.compile(r"^(叶修|万维钢)([·・].*)?$")
MARKETING_PATTERNS = (
    "一个研究 思维方法 与 学习策略 的人",
    "新来的朋友点击上方 蓝字 关注",
    "即可免费获得深度思维、高效学习的方法",
    "这个广告每篇文章后面都有，就不多说了",
    "购课相关咨询请添加",
    "报名链接",
    "试听课链接",
    "写留言",
)


def read_markdown_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.replace("\ufeff", "").replace("\r\n", "\n")


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if not line.strip():
            blank_run += 1
            if blank_run <= 1:
                cleaned.append("")
            continue
        blank_run = 0
        cleaned.append(re.sub(r"\s+", " ", line).strip())
    return "\n".join(cleaned).strip()


def split_sentences(text: str) -> list[str]:
    normalized = clean_text(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def parse_markdown_document(text: str) -> tuple[str, list[SectionRecord]]:
    lines = text.splitlines()
    title = ""
    sections: list[SectionRecord] = []
    current_title: str | None = None
    current_source_url: str | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_title, current_source_url, current_lines
        if not current_title:
            return
        section_text = clean_text("\n".join(current_lines))
        sections.append(
            SectionRecord(
                title=current_title,
                source_url=current_source_url,
                text=section_text,
            )
        )
        current_title = None
        current_source_url = None
        current_lines = []

    for raw_line in lines:
        if not title:
            match = H1_RE.match(raw_line)
            if match:
                title = match.group(1).strip()
                continue
        h2_match = H2_RE.match(raw_line)
        if h2_match:
            flush_current()
            current_title = h2_match.group(1).strip()
            current_source_url = None
            current_lines = []
            continue
        source_match = SOURCE_LINE_RE.match(raw_line.strip())
        if current_title and source_match and current_source_url is None:
            current_source_url = source_match.group(1).strip()
            continue
        if current_title:
            current_lines.append(raw_line)

    flush_current()

    if not title:
        raise ValueError("Markdown document is missing an H1 title.")
    return title, sections


def extract_char_count(sections: list[SectionRecord]) -> int:
    return sum(len(section.text) for section in sections)


def section_text_preview(section: SectionRecord, limit: int = 200) -> str:
    text = clean_text(section.text)
    return text[:limit]


def clean_section_text(source: str, title: str, text: str) -> str:
    lines = clean_text(text).splitlines()
    cleaned: list[str] = []
    skip_leading = True
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue

        if source == "jingyingrike":
            if skip_leading and (line == "万维钢·精英日课" or line == title or TIMESTAMP_LINE_RE.match(line) or NARRATOR_LINE_RE.match(line)):
                continue
        if source == "yexiu_wechat":
            if skip_leading and (SOURCE_PROMO_RE.match(line) or any(pattern in line for pattern in MARKETING_PATTERNS)):
                continue
            if any(pattern in line for pattern in MARKETING_PATTERNS):
                continue

        skip_leading = False
        cleaned.append(line)

    normalized = "\n".join(cleaned).strip()
    if source == "yexiu_wechat":
        for marker in ["进击之心——挣脱命运牢笼的信念课：", "对学生来说，自然就是指的我的学习策略课程"]:
            position = normalized.find(marker)
            if position > 0:
                normalized = normalized[:position].rstrip()
                break
    return clean_text(normalized)
