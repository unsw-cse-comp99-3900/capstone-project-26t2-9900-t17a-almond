from __future__ import annotations

import unittest
from pathlib import Path

from robustness_experiments.code.code_perturbations import apply_control_wrapper, dataset_slug, is_probably_declaration


class ControlWrapperTests(unittest.TestCase):
    def test_dataset_slug_uses_input_directory_or_file_parent(self) -> None:
        self.assertEqual(dataset_slug(Path("input_sources/cwe119")), "cwe119")
        self.assertEqual(dataset_slug(Path("input_sources/devign/sample.c")), "devign")

    def test_custom_type_declaration_is_not_wrapped(self) -> None:
        source = """int sample(void)
{
    Widget *item;
    value = read_value();
    return value;
}
"""

        result = apply_control_wrapper(source)

        self.assertEqual(result.applied_count, 1)
        self.assertTrue(is_probably_declaration("Widget *item;"))
        self.assertIn("    Widget *item;\n    if (1) {\n        value = read_value();\n    }", result.source_text)

    def test_non_declaration_expression_statements_remain_candidates(self) -> None:
        source = """int sample(void)
{
    Widget *item;
    return item;
}
"""

        result = apply_control_wrapper(source)

        for statement in (
            "return item;",
            "goto cleanup;",
            "new Widget;",
            "sizeof item;",
            "co_yield item;",
            "co_await task;",
        ):
            with self.subTest(statement=statement):
                self.assertFalse(is_probably_declaration(statement))
        self.assertIn("    if (1) {\n        return item;\n    }", result.source_text)


if __name__ == "__main__":
    unittest.main()
