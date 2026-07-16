"""Shared DOM contract for pitching player metric cards.

The pitching builder owns the card markup. Downstream report assembly and
final batting polish validate that markup through this module instead of
maintaining independent copies of the same rules.
"""

from __future__ import annotations

import re


PITCH_REFERENCE_CLASS = "pitch-coach-reference"
PLAYER_PITCH_HEADING = '<div class="section-title"><span class="mark"></span><h3>投球</h3></div>'
COACH_VIEW_HEADING = '<div class="section-title"><span class="mark"></span><h2>教练视角</h2></div>'

_CARD_PATTERN = re.compile(
    r'<article class="metric-card\b[^>]*>.*?</article>',
    flags=re.DOTALL,
)


def extract_combined_player_pitch(html_text: str) -> str:
    """Return only the player-view pitching fragment from a combined report."""
    if PLAYER_PITCH_HEADING not in html_text:
        raise RuntimeError("Combined report is missing the player pitching section.")
    start = html_text.index(PLAYER_PITCH_HEADING)
    try:
        end = html_text.index(COACH_VIEW_HEADING, start)
    except ValueError as exc:
        raise RuntimeError("Combined report is missing the coach-view heading after player pitching.") from exc
    return html_text[start:end]


def validate_pitch_player_cards(fragment: str, context: str) -> int:
    """Require one coach-reference box above the peer range in every card."""
    cards = _CARD_PATTERN.findall(fragment)
    if not cards:
        raise RuntimeError(f"{context}: no pitching player metric cards found.")

    failures: list[str] = []
    reference_token = f'<div class="{PITCH_REFERENCE_CLASS}">'
    for index, card in enumerate(cards, start=1):
        reference_count = card.count(f'class="{PITCH_REFERENCE_CLASS}"')
        detail_at = card.find('<div class="metric-detail">')
        reference_at = card.find(reference_token)
        range_at = card.find('<div class="peer-range')
        reference_end = card.find("</div>", reference_at) + len("</div>") if reference_at >= 0 else -1
        adjacent = bool(
            reference_end > 0
            and range_at >= reference_end
            and not card[reference_end:range_at].strip()
        )
        if reference_count != 1:
            failures.append(f"card {index}: references={reference_count}")
        elif not (0 <= detail_at < reference_at < reference_end <= range_at):
            failures.append(f"card {index}: expected metric-detail -> reference -> peer-range")
        elif not adjacent:
            failures.append(f"card {index}: reference is not immediately before peer-range")

    if failures:
        raise RuntimeError(f"{context}: pitching player-card contract failed: " + "; ".join(failures))
    return len(cards)


def pitch_reference_count(fragment: str) -> int:
    return fragment.count(f'class="{PITCH_REFERENCE_CLASS}"')
