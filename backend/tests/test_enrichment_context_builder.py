"""Evidence context assembly caps."""

from __future__ import annotations

from app.core.enrichment_pipeline_config import RetrievalStageConfig
from app.services.enrichment.context_builder import build_evidence_context


class _Ev:
    def __init__(self, title: str, body: str) -> None:
        self.id = "00000000-0000-0000-0000-000000000001"
        self.title = title
        self.summary = body
        self.cleaned_content = None


def test_context_respects_line_and_char_caps() -> None:
    retrieval = RetrievalStageConfig(
        evidence_line_limit=2,
        excerpt_max_chars=80,
        context_max_chars=500,
        digest_line_limit=1,
    )
    rows = [_Ev("A", "x" * 100), _Ev("B", "y" * 100), _Ev("C", "z" * 100)]
    bundle = build_evidence_context(
        evidence_rows=rows,
        url_blocks=[],
        retrieval=retrieval,
        empty_digest_prompt="empty",
    )
    assert len(bundle.lines) == 2
    assert len(bundle.context) <= 500
    assert bundle.digest != "empty"
