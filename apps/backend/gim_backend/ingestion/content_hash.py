

from __future__ import annotations

import hashlib


def compute_content_hash(node_id: str, title: str, body_text: str) -> str:
    content = f"{node_id}:{title}:{body_text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

