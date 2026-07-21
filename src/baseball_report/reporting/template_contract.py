from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from baseball_report.core.errors import ReportBuildError


CANONICAL_TEMPLATE_REPO_PATH = "reports/pitching_bryan_coach/index.html"
CANONICAL_TEMPLATE_SHA256 = "2b2c39e55f3c4ad87c21784db0d5b705b9f8c33aa1a13bf36bf7a38d46dfad21"


@dataclass(frozen=True)
class TemplateShape:
    section_count: int
    metric_card_count: int
    peer_range_count: int


CANONICAL_TEMPLATE_SHAPE = TemplateShape(7, 16, 28)


def template_sha256(html_text: str) -> str:
    return hashlib.sha256(html_text.encode("utf-8")).hexdigest()


def template_shape(html_text: str) -> TemplateShape:
    return TemplateShape(
        section_count=len(re.findall(r"<section\b", html_text)),
        metric_card_count=len(re.findall(r'<article class="metric-card\b', html_text)),
        peer_range_count=len(re.findall(r'class="peer-range\b', html_text)),
    )


def validate_canonical_template(html_text: str, *, require_exact_blob: bool = False) -> TemplateShape:
    shape = template_shape(html_text)
    if shape != CANONICAL_TEMPLATE_SHAPE:
        raise ReportBuildError(
            f"canonical template DOM shape changed: expected {CANONICAL_TEMPLATE_SHAPE}, got {shape}"
        )
    if require_exact_blob and template_sha256(html_text) != CANONICAL_TEMPLATE_SHA256:
        raise ReportBuildError("canonical template content hash changed without a contract update")
    return shape
