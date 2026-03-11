from __future__ import annotations

import re
from collections import defaultdict

from models import CatalogEntry


TOPIC_PATTERN = re.compile(r"《(?P<topic>[^》]+)》")
QA_PATTERN = re.compile(r"^\s*(问答|答疑|Q&A|QA)\s*[:：]?", re.IGNORECASE)
PREFACE_PATTERN = re.compile(r"^\s*发刊词")
SEASON_ENDING_PATTERN = re.compile(r"^\s*(第[0-9一二三四五六七八九十]+季结束语)")
SECTION_COUNT_SUFFIX_PATTERN = re.compile(r"\s*[（(]\s*\d+\s*讲\s*[)）]\s*$")
SECTION_DECORATION_PATTERN = re.compile(r"^[*#\-\s]+|[*#\-\s]+$")
SKIP_SECTION_TOPICS = {"特别放送"}


def extract_topic(title: str) -> str | None:
    match = TOPIC_PATTERN.search(title)
    if not match:
        return None
    topic = match.group("topic").strip()
    return topic or None


def is_qa_title(title: str) -> bool:
    return bool(QA_PATTERN.match(title))


def normalize_section_topic(raw_section_title: str | None) -> str | None:
    if not raw_section_title:
        return None

    section = raw_section_title.strip()
    if not section:
        return None

    section = SECTION_COUNT_SUFFIX_PATTERN.sub("", section).strip()
    section = SECTION_DECORATION_PATTERN.sub("", section).strip()

    quoted = extract_topic(section)
    if quoted:
        return quoted

    return section or None


def extract_special_topic(title: str) -> str | None:
    if PREFACE_PATTERN.match(title):
        return "发刊词"
    match = SEASON_ENDING_PATTERN.match(title)
    if match:
        return match.group(1)
    return None


def should_use_section_topic(section_topic: str | None) -> bool:
    return bool(section_topic and section_topic not in SKIP_SECTION_TOPICS)


def assign_topics(entries: list[CatalogEntry]) -> tuple[list[CatalogEntry], list[CatalogEntry]]:
    assigned: list[CatalogEntry] = []
    unassigned: list[CatalogEntry] = []
    current_topic: str | None = None

    for entry in sorted(entries, key=lambda item: item.order):
        title_topic = extract_topic(entry.title)
        section_topic = normalize_section_topic(entry.section_topic)
        special_topic = extract_special_topic(entry.title)

        entry.raw_topic = title_topic
        entry.section_topic = section_topic
        entry.is_qa = is_qa_title(entry.title)

        if special_topic:
            entry.assigned_topic = special_topic
            assigned.append(entry)
            continue

        if should_use_section_topic(section_topic):
            entry.assigned_topic = section_topic
            current_topic = section_topic
            assigned.append(entry)
            continue

        if title_topic:
            entry.assigned_topic = title_topic
            current_topic = title_topic
            assigned.append(entry)
            continue

        if entry.is_qa and current_topic:
            entry.assigned_topic = current_topic
            assigned.append(entry)
            continue

        entry.assigned_topic = None
        unassigned.append(entry)

    return assigned, unassigned


def group_entries_by_topic(entries: list[CatalogEntry]) -> dict[str, list[CatalogEntry]]:
    grouped: dict[str, list[CatalogEntry]] = defaultdict(list)
    for entry in sorted(entries, key=lambda item: item.order):
        if entry.assigned_topic:
            grouped[entry.assigned_topic].append(entry)
    return dict(grouped)


def ordered_topic_names(entries: list[CatalogEntry]) -> list[str]:
    grouped = group_entries_by_topic(entries)
    return sorted(grouped, key=lambda topic: min(item.order for item in grouped[topic]))


def select_topic_names(
    entries: list[CatalogEntry],
    *,
    topic: str | None = None,
    start_after_topic: str | None = None,
    start_topic: str | None = None,
    end_topic: str | None = None,
    topic_limit: int | None = None,
) -> list[str]:
    topic_names = ordered_topic_names(entries)
    if topic and any(value is not None for value in (start_after_topic, start_topic, end_topic)):
        raise ValueError("--topic cannot be combined with range selection options")
    if start_after_topic and start_topic:
        raise ValueError("--start-after-topic and --start-topic cannot be used together")

    if topic:
        return [topic] if topic in topic_names else []

    start_index = 0
    if start_after_topic:
        if start_after_topic not in topic_names:
            raise ValueError(f"Unknown topic: {start_after_topic}")
        start_index = topic_names.index(start_after_topic) + 1
    elif start_topic:
        if start_topic not in topic_names:
            raise ValueError(f"Unknown topic: {start_topic}")
        start_index = topic_names.index(start_topic)

    selected = topic_names[start_index:]
    if end_topic:
        if end_topic not in topic_names:
            raise ValueError(f"Unknown topic: {end_topic}")
        end_index = topic_names.index(end_topic)
        if end_index < start_index:
            raise ValueError("--end-topic must not be earlier than the selected start topic")
        selected = topic_names[start_index : end_index + 1]
    if topic_limit is not None:
        selected = selected[:topic_limit]
    return selected
