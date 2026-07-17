from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from youtube_breakout.common import load_channel_watchlist


class WatchlistLoaderTests(unittest.TestCase):
    def test_loads_enabled_extra_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "channels.yaml"
            path.write_text(
                """
direct:
  - name: Core
    url: https://www.youtube.com/@core/videos
    enabled: true
weekly_exploratory_test_ring:
  - name: Enabled Test
    url: https://www.youtube.com/@enabled/videos
    enabled: true
    cadence: weekly_test
    tags: [ai-agents]
  - name: Disabled Test
    url: https://www.youtube.com/@disabled/videos
    enabled: false
""".strip()
                + "\n",
                encoding="utf-8",
            )
            rows = load_channel_watchlist(path)
        names = [row["name"] for row in rows]
        self.assertEqual(names, ["Core", "Enabled Test"])
        self.assertEqual(rows[1]["layer"], "weekly_exploratory_test_ring")
        self.assertEqual(rows[1]["cadence"], "weekly_test")
        self.assertEqual(rows[1]["tags"], ["ai-agents"])


if __name__ == "__main__":
    unittest.main()
