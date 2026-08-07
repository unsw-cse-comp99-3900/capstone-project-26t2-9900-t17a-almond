import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import deepwukong_console as console


class DashboardMenuTests(unittest.TestCase):
    def test_console_displays_the_shared_graph_budget_configuration(self):
        self.assertEqual(
            console.GRAPH_BUDGET_LABEL,
            "1/3/5/7/9/11/13/15/20/25",
        )

    def test_selected_dashboard_opens_then_returns_to_dashboard_menu(self):
        with (
            patch("builtins.input", side_effect=["2", "0"]),
            patch("builtins.print"),
            patch.dict(console.os.environ, {"ALMOND_DASHBOARD_BASE_URL": ""}, clear=False),
            patch.object(console, "print_header") as print_header,
            patch.object(console, "pause") as pause,
            patch.object(console.webbrowser, "open") as open_browser,
        ):
            console.open_web_dashboard()

        open_browser.assert_called_once_with(console.PDG_ATLAS_HTML.resolve().as_uri())
        pause.assert_not_called()
        self.assertEqual(print_header.call_count, 2)

    def test_latest_graph_comparison_is_added_without_changing_existing_options(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            latest = project_root / "outputs" / "run_20260730_test" / "graph_comparison" / "dashboard.html"
            latest.parent.mkdir(parents=True)
            latest.write_text("<html></html>", encoding="utf-8")
            with (
                patch("builtins.input", side_effect=["3", "0"]),
                patch("builtins.print"),
                patch.dict(console.os.environ, {"ALMOND_DASHBOARD_BASE_URL": ""}, clear=False),
                patch.object(console, "PROJECT_ROOT", project_root),
                patch.object(console, "print_header"),
                patch.object(console.webbrowser, "open") as open_browser,
            ):
                console.open_web_dashboard()

        open_browser.assert_called_once_with(latest.resolve().as_uri())
