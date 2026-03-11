from __future__ import annotations

from pathlib import Path

import yaml

from models import Taxonomy
from settings import PATHS


def load_taxonomy(path: Path | None = None) -> Taxonomy:
    taxonomy_path = path or PATHS.taxonomy_path
    with taxonomy_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return Taxonomy(
        primary_categories=data["primary_categories"],
        topic_groups=data["topic_tags"],
        attribute_groups=data["attribute_tags"],
        rules=data["rules"],
        keyword_hints=data["keyword_hints"],
    )


def validate_primary_label(taxonomy: Taxonomy, label: str) -> bool:
    return label in taxonomy.primary_categories


def validate_topic_labels(taxonomy: Taxonomy, labels: list[str]) -> bool:
    allowed = set(taxonomy.topic_tags)
    return all(label in allowed for label in labels)


def validate_attribute_labels(taxonomy: Taxonomy, labels: list[str]) -> bool:
    allowed = set(taxonomy.attribute_tags)
    return all(label in allowed for label in labels)


def deduplicate_topic_labels(taxonomy: Taxonomy, labels: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    synonym_groups = taxonomy.rules.get("synonym_dedup", {})
    blocked: set[str] = set()
    for label in labels:
        if label in seen or label in blocked:
            continue
        output.append(label)
        seen.add(label)
        blocked.update(synonym_groups.get(label, []))
    return output


def group_for_topic_tag(taxonomy: Taxonomy, label: str) -> str | None:
    for group_name, labels in taxonomy.topic_groups.items():
        if label in labels:
            return group_name
    return None
