from __future__ import annotations

from collections import OrderedDict

from models import ArticleRecord, DirectoryEntry


def group_entries(entries: list[DirectoryEntry]) -> "OrderedDict[tuple[str, str], list[DirectoryEntry]]":
    grouped: "OrderedDict[tuple[str, str], list[DirectoryEntry]]" = OrderedDict()
    for entry in sorted(entries, key=lambda item: item.order):
        grouped.setdefault((entry.category, entry.section), []).append(entry)
    return grouped


def group_records(records: list[ArticleRecord]) -> "OrderedDict[tuple[str, str], list[ArticleRecord]]":
    grouped: "OrderedDict[tuple[str, str], list[ArticleRecord]]" = OrderedDict()
    for record in sorted(records, key=lambda item: item.order):
        grouped.setdefault((record.category, record.section), []).append(record)
    return grouped


def ordered_catalog_lines(entries: list[DirectoryEntry]) -> list[str]:
    lines: list[str] = []
    for index, ((category, section), grouped_entries) in enumerate(group_entries(entries).items(), start=1):
        label = category if category == section else f"{category} / {section}"
        lines.append(f"{index:>3}. {label} | {len(grouped_entries)} articles")
    return lines


def select_entries(entries: list[DirectoryEntry], *, category: str | None = None, section: str | None = None) -> list[DirectoryEntry]:
    filtered = entries
    if category:
        filtered = [entry for entry in filtered if entry.category == category]
    if section:
        filtered = [entry for entry in filtered if entry.section == section]
    return filtered
