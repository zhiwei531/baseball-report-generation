import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pitching.player_card_contract import (  # noqa: E402
    COACH_VIEW_HEADING,
    PLAYER_PITCH_HEADING,
    extract_combined_player_pitch,
    validate_pitch_player_cards,
)


def card(reference_position: str = "detail") -> str:
    reference = '<div class="pitch-coach-reference"><b>阿楽教练</b><span>42°</span></div>'
    summary_reference = reference if reference_position == "summary" else ""
    detail_reference = reference if reference_position == "detail" else ""
    return f'''<article class="metric-card good">
      <div class="metric-summary"><div class="metric-value">40°</div>{summary_reference}</div>
      <div class="metric-detail"><p>说明</p>{detail_reference}<div class="peer-range"><div></div></div></div>
    </article>'''


class PitchPlayerCardContractTests(unittest.TestCase):
    def test_accepts_reference_above_peer_range(self) -> None:
        self.assertEqual(validate_pitch_player_cards(card(), "test"), 1)

    def test_rejects_reference_in_summary(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "metric-detail"):
            validate_pitch_player_cards(card("summary"), "test")

    def test_rejects_missing_reference(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "references=0"):
            validate_pitch_player_cards(card("missing"), "test")

    def test_extracts_only_player_pitch_section(self) -> None:
        html = PLAYER_PITCH_HEADING + card() + COACH_VIEW_HEADING + card("missing")
        fragment = extract_combined_player_pitch(html)
        self.assertEqual(validate_pitch_player_cards(fragment, "combined"), 1)


if __name__ == "__main__":
    unittest.main()
