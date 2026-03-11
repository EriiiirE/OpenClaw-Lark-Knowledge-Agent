from __future__ import annotations

from typing import Iterable

from models import DocumentRecord, ReviewItem


def iter_review_targets(review_items: list[ReviewItem], limit: int | None = None, doc_id: str | None = None) -> Iterable[ReviewItem]:
    items = review_items
    if doc_id:
        items = [item for item in items if item.doc_id == doc_id]
    if limit is not None:
        items = items[:limit]
    return items


def apply_review_updates(
    documents: list[DocumentRecord],
    review_items: list[ReviewItem],
    limit: int | None = None,
    doc_id: str | None = None,
) -> tuple[list[DocumentRecord], list[ReviewItem]]:
    target_ids = {item.doc_id for item in iter_review_targets(review_items, limit=limit, doc_id=doc_id)}
    remaining = [item for item in review_items if item.doc_id not in target_ids]
    for document in documents:
        if document.doc_id not in target_ids:
            continue
        print(f"\nReviewing: {document.title}")
        print(f"  file_path: {document.file_path}")
        print(f"  primary_category: {document.primary_category}")
        print(f"  topic_tags: {', '.join(document.topic_tags)}")
        print(f"  attribute_tags: {', '.join(document.attribute_tags)}")
        print(f"  summary: {document.summary}")

        new_primary = input("New primary category (blank to keep): ").strip()
        if new_primary:
            document.primary_category = new_primary
        new_topics = input("New topic tags comma-separated (blank to keep): ").strip()
        if new_topics:
            document.topic_tags = [item.strip() for item in new_topics.split(",") if item.strip()]
        new_attributes = input("New attribute tags comma-separated (blank to keep): ").strip()
        if new_attributes:
            document.attribute_tags = [item.strip() for item in new_attributes.split(",") if item.strip()]
        new_summary = input("New summary (blank to keep): ").strip()
        if new_summary:
            document.summary = new_summary
        document.review_required = False
        document.review_reason = None
    return documents, remaining
