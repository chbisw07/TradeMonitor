"""Small persistent Attention queue used by the TM1/TGT3 control room."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from trademonitor.domain.enums import AttentionLevel, AttentionStatus
from trademonitor.domain.models import AttentionItem


def create_attention_item(
    *,
    level: AttentionLevel | str,
    source: str,
    title: str,
    detail: str,
) -> AttentionItem:
    return AttentionItem(
        attention_id=str(uuid4()),
        level=AttentionLevel(level).value,
        source=source.upper(),
        title=title,
        detail=detail,
        status=AttentionStatus.OPEN.value,
        created_at=datetime.now(UTC),
    )


def resolve_attention_item(item: AttentionItem) -> AttentionItem:
    return AttentionItem(
        attention_id=item.attention_id,
        level=item.level,
        source=item.source,
        title=item.title,
        detail=item.detail,
        status=AttentionStatus.RESOLVED.value,
        created_at=item.created_at,
        resolved_at=datetime.now(UTC),
    )
