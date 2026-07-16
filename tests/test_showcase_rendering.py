from __future__ import annotations

import unittest

from demo_b.showcase.generate_showcase import render_inline_diff


class ShowcaseRenderingTests(unittest.TestCase):
    def test_inline_diff_keeps_full_source_and_omits_blank_rows(self) -> None:
        rendered = render_inline_diff(
            "first();\n\nold();\nlast();\n",
            "first();\n\nnew();\nlast();\n",
        )

        self.assertEqual(rendered.count('class="inline-line'), 5)
        self.assertNotIn('class="inline-code"></span>', rendered)
        self.assertIn('diff-remove', rendered)
        self.assertIn('>old();</span>', rendered)
        self.assertIn('diff-add', rendered)
        self.assertIn('>new();</span>', rendered)
        self.assertIn('>last();</span>', rendered)

    def test_inline_diff_preserves_original_and_selected_line_numbers(self) -> None:
        rendered = render_inline_diff("first();\nsecond();\n", "first();\ninserted();\nsecond();\n")

        self.assertIn('<span class="inline-number" aria-hidden="true">2</span>', rendered)
        self.assertIn('<span class="inline-marker" aria-hidden="true">+</span>', rendered)
        self.assertIn('>inserted();</span>', rendered)


if __name__ == "__main__":
    unittest.main()
