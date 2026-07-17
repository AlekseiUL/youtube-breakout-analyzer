from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from youtube_breakout import yt_breakout_analyzer as analyzer
from youtube_breakout import yt_breakout_fixture as fixture


WALKING_CONFIG = ROOT / "configs" / "niches" / "walking.yaml"
AI_CONFIG = ROOT / "configs" / "niches" / "ai-automation.yaml"


class BreakoutAnalyzerTests(unittest.TestCase):
    def analyze(self, project_root: Path, config: Path, mode: str = "full-public") -> dict:
        return analyzer.analyze_project(analyzer.AnalysisOptions(
            project_root=project_root,
            niche_config=config,
            limit_per_channel=30,
            top_outliers=25,
            mode=mode,
            analysis_at=fixture.FIXTURE_AT,
            run_id=f"test-{config.stem}-{mode.replace('+', '-')}",
        ))

    def test_thresholds_and_ranking_favor_small_channel_multiplier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture.write_fixture_project(root)
            result = self.analyze(root, WALKING_CONFIG)
        ranked = result["ranked_outliers"]
        self.assertGreaterEqual(len(ranked), 3)
        self.assertEqual(ranked[0]["video_id"], "walk_tokyo_rain")
        self.assertEqual(ranked[0]["channel_outlier_multiplier"], 24.0)
        self.assertEqual(ranked[0]["breakout_status"], "EXTREME_BREAKOUT")
        self.assertIn("20x+ extreme", ranked[0]["channel_outlier_tier"])
        self.assertEqual(ranked[1]["video_id"], "walk_seoul_snow")
        self.assertEqual(ranked[2]["video_id"], "walk_paris_night")
        self.assertGreater(ranked[1]["channel_outlier_multiplier"], ranked[2]["channel_outlier_multiplier"])
        self.assertGreater(ranked[2]["views"], ranked[1]["views"])

    def test_insufficient_baseline_does_not_fabricate_multiplier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture.write_fixture_project(root)
            result = self.analyze(root, WALKING_CONFIG)
        by_id = {item["video_id"]: item for item in result["videos"]}
        weak = by_id["walk_new_insufficient"]
        self.assertEqual(weak["channel_baseline_status"], "INSUFFICIENT_CHANNEL_BASELINE")
        self.assertIsNone(weak["channel_outlier_multiplier"])
        self.assertNotIn("walk_new_insufficient", {item["video_id"] for item in result["ranked_outliers"]})

    def test_plugin_separation_between_walking_and_ai_automation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture.write_fixture_project(root)
            walking = self.analyze(root, WALKING_CONFIG)
            ai = self.analyze(root, AI_CONFIG)
        self.assertTrue(all(pattern["niche"] == "walking" for pattern in walking["patterns"]))
        self.assertTrue(all(pattern["niche"] == "ai-automation" for pattern in ai["patterns"]))
        self.assertIn("walk_tokyo_rain", {item["video_id"] for item in walking["ranked_outliers"]})
        self.assertNotIn("ai_n8n_invoice", {item["video_id"] for item in walking["videos"]})
        self.assertIn("ai_n8n_invoice", {item["video_id"] for item in ai["ranked_outliers"]})
        self.assertNotIn("walk_tokyo_rain", {item["video_id"] for item in ai["videos"]})
        self.assertFalse(any(pattern["pattern"] == "weather: rain" for pattern in ai["patterns"]))

    def test_walking_pattern_grouping_has_counterexamples_and_association_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture.write_fixture_project(root)
            result = self.analyze(root, WALKING_CONFIG)
        rain = next(pattern for pattern in result["patterns"] if pattern["pattern"] == "weather: rain")
        self.assertGreaterEqual(rain["evidence_count"], 2)
        self.assertGreaterEqual(rain["channels_count"], 2)
        self.assertIn(rain["confidence"], {"MEDIUM", "HIGH"})
        self.assertTrue(rain["counterexamples"])
        self.assertEqual(rain["causality_warning"], analyzer.CAUSALITY_WARNING)

    def test_reports_include_required_sections_and_no_causal_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture.write_fixture_project(root)
            self.analyze(root, WALKING_CONFIG)
            report = (root / "result" / "breakout-report.md").read_text(encoding="utf-8")
            playbook = (root / "result" / "shooting-playbook.md").read_text(encoding="utf-8")
        for section in [
            "## Verdict",
            "## Data coverage and access gaps",
            "## Top small-channel breakouts",
            "## Top established-channel breakouts",
            "## Cross-channel patterns",
            "## Niche-specific patterns",
            "## Counterexamples / killed hypotheses",
            "## Facts vs interpretation",
            "## Main caveat",
            "## Recommended experiments",
            "## Confidence",
        ]:
            self.assertIn(section, report)
        self.assertIn("association, not proven cause", report)
        self.assertNotIn(" caused ", report.lower())
        self.assertIn("Viewer job:", playbook)
        self.assertIn("What is hypothesis vs proven repetition:", playbook)

    def test_degraded_metadata_only_mode_reports_not_requested_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture.write_fixture_project(root)
            result = self.analyze(root, WALKING_CONFIG, mode="metadata-only")
        coverage = result["data_coverage"]["summary"]
        self.assertEqual(coverage["comments"], {"NOT_REQUESTED": result["facts"]["videos_analyzed"]})
        self.assertEqual(coverage["visual"], {"NOT_REQUESTED": result["facts"]["videos_analyzed"]})
        self.assertEqual(coverage["transcripts"], {"NOT_REQUESTED": result["facts"]["videos_analyzed"]})
        first = result["videos"][0]
        self.assertEqual(first["data_coverage"]["comments"], "NOT_REQUESTED")

    def test_fixture_cli_produces_required_latest_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "youtube_breakout.cli",
                    "fixture",
                    "--project-root",
                    str(root),
                    "--niche",
                    "walking",
                    "--force",
                ],
                cwd=str(ROOT),
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["niche"], "walking")
            latest = json.loads((root / "result" / "breakout-analysis.json").read_text(encoding="utf-8"))
            run_copy = json.loads(
                (root / "result" / "breakout-runs" / "fixture-walking" / "breakout-analysis.json").read_text(encoding="utf-8")
            )
            original_run_copy = json.dumps(run_copy, sort_keys=True)
            self.assertEqual(latest["outputs"], run_copy["outputs"])
            for rel in [
                "result/breakout-analysis.json",
                "result/breakout-analysis.csv",
                "result/breakout-report.md",
                "result/content-playbook.md",
                "result/shooting-playbook.md",
                "result/PATTERN_BANK.json",
                "result/PATTERN_BANK.md",
                "result/source-ledger.json",
                "result/source-ledger.csv",
                "result/breakout-visual-manifest.json",
                "result/breakout-latest.json",
            ]:
                self.assertTrue((root / rel).exists(), rel)

            refused = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "youtube_breakout.cli",
                    "fixture",
                    "--project-root",
                    str(root),
                    "--niche",
                    "walking",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("rerun with --force", refused.stderr)

            forced = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "youtube_breakout.cli",
                    "fixture",
                    "--project-root",
                    str(root),
                    "--niche",
                    "walking",
                    "--force",
                ],
                cwd=str(ROOT),
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(forced.stdout)["niche"], "walking")
            second_run = root / "result" / "breakout-runs" / "fixture-walking-2" / "breakout-analysis.json"
            self.assertTrue(second_run.exists())
            preserved = json.loads(
                (root / "result" / "breakout-runs" / "fixture-walking" / "breakout-analysis.json").read_text(encoding="utf-8")
            )
            self.assertEqual(json.dumps(preserved, sort_keys=True), original_run_copy)

    def test_all_public_modes_preserve_explicit_coverage(self) -> None:
        expectations = {
            "metadata-only": ("NOT_REQUESTED", "NOT_REQUESTED", "NOT_REQUESTED"),
            "metadata+comments": (None, "NOT_REQUESTED", "NOT_REQUESTED"),
            "metadata+visual": ("NOT_REQUESTED", None, "NOT_REQUESTED"),
            "full-public": (None, None, None),
        }
        for mode, expected in expectations.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                fixture.write_fixture_project(root)
                result = self.analyze(root, WALKING_CONFIG, mode=mode)
                row = result["videos"][0]["data_coverage"]
                for field, value in zip(("comments", "visual", "transcripts"), expected):
                    if value is not None:
                        self.assertEqual(row[field], value)
                    else:
                        self.assertNotEqual(row[field], "NOT_REQUESTED")

    def test_pattern_bank_and_source_ledger_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture.write_fixture_project(root)
            result = self.analyze(root, WALKING_CONFIG, mode="full-public")
            bank = result["PATTERN_BANK"]
            self.assertEqual(set(bank["categories"]), {
                "title_formulas", "thumbnail_formulas", "content_formats", "audience_promises",
                "emotional_hooks", "comment_motivations", "saturation_signals", "opportunity_gaps",
                "counter_patterns", "avoid_copying",
            })
            self.assertTrue(bank["all_patterns"])
            first = bank["all_patterns"][0]
            for field in [
                "evidence_count", "channels_count", "median_breakout_multiplier", "examples",
                "counterexamples", "production_hypothesis", "confidence", "known", "unknown",
                "next_test", "causality_warning",
            ]:
                self.assertIn(field, first)
            self.assertEqual(first["causality_warning"], "association, not proven cause")
            ledger = json.loads((root / "result/source-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger), result["facts"]["videos_analyzed"])
            self.assertIn("metadata_status", ledger[0])


if __name__ == "__main__":
    unittest.main()
