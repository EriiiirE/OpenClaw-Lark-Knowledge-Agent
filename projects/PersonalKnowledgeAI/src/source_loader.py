from __future__ import annotations

from pathlib import Path

from settings import CELUESHI_ROOT, JINGYINGRIKE_ROOT, PATHS


def iter_markdown_sources() -> list[tuple[str, Path, str]]:
    items: list[tuple[str, Path, str]] = []
    for root, source, relative_base in [
        (JINGYINGRIKE_ROOT, "jingyingrike", JINGYINGRIKE_ROOT.parents[1]),
        (CELUESHI_ROOT, "yexiu_wechat", CELUESHI_ROOT.parents[1]),
        (PATHS.knowledge_dir, "local_knowledge", PATHS.base_dir),
    ]:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if source == "local_knowledge" and path.name.lower() == "readme.md":
                continue
            relative = str(path.relative_to(relative_base).as_posix())
            items.append((source, path, relative))
    return items
