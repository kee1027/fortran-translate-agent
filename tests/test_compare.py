import unittest

from src.eval.compare import compare_outputs, extract_numbers, normalize_text


class CompareOutputTests(unittest.TestCase):
    def test_extract_numbers(self) -> None:
        self.assertEqual(extract_numbers("a 1.5 b -2e-3 c 4\n"), [1.5, -0.002, 4.0])

    def test_text_normalization(self) -> None:
        self.assertEqual(normalize_text("a  \r\nb\r\n"), "a\nb")

    def test_numeric_match(self) -> None:
        result = compare_outputs("10.0000001\n", "10.0\n", comparison="numeric", rel_tolerance=1e-6)
        self.assertTrue(result.passed)

    def test_numeric_mismatch(self) -> None:
        result = compare_outputs("10.1\n", "10.0\n", comparison="numeric", rel_tolerance=1e-9, abs_tolerance=1e-12)
        self.assertFalse(result.passed)

    def test_numeric_or_text_fallback(self) -> None:
        result = compare_outputs("hello\n", "hello\n", comparison="numeric_or_text")
        self.assertTrue(result.passed)
        self.assertEqual(result.mode, "numeric_or_text:text")


if __name__ == "__main__":
    unittest.main()
