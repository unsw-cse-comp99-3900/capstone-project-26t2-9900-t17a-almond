import unittest
from unittest.mock import patch

import deepwukong_demo_console_v4 as console


class DashboardMenuTests(unittest.TestCase):
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
