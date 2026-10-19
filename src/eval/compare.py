"""Output comparison helpers for Fortran -> C++ verification."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

NUMBER_RE = re.compile(
    r"(?P<number>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?|[-+]?(?:nan|inf(?:inity)?))",
    re.IGNORECASE,
)


@dataclass
class ComparisonResult:
    passed: bool
    mode: str
    message: str
    expected_numbers: list[float] = field(default_factory=list)
    actual_numbers: list[float] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """Normalize line endings and trailing whitespace for text comparison."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n")


def extract_numbers(text: str) -> list[float]:
    """Extract numeric tokens from text output."""
    values: list[float] = []
    for match in NUMBER_RE.finditer(text):
        token = match.group("number")
        lowered = token.lower()
        if "nan" in lowered:
            values.append(float("nan"))
        elif "inf" in lowered:
            values.append(float("-inf") if token.startswith("-") else float("inf"))
        else:
            values.append(float(token))
    return values


def _numbers_close(left: float, right: float, rel_tolerance: float, abs_tolerance: float) -> bool:
    if math.isnan(left) or math.isnan(right):
        return math.isnan(left) and math.isnan(right)
    if math.isinf(left) or math.isinf(right):
        return left == right
    return math.isclose(left, right, rel_tol=rel_tolerance, abs_tol=abs_tolerance)


def compare_outputs(
    actual: str,
    expected: str,
    comparison: str = "numeric_or_text",
    rel_tolerance: float = 1.0e-9,
    abs_tolerance: float = 1.0e-12,
) -> ComparisonResult:
    """Compare actual and expected output using the requested mode."""
    if comparison not in {"text", "numeric", "numeric_or_text", "custom"}:
        return ComparisonResult(False, comparison, f"unsupported comparison mode: {comparison}")

    if comparison == "custom":
        return ComparisonResult(False, comparison, "custom comparison is not implemented")

    if comparison in {"numeric", "numeric_or_text"}:
        expected_numbers = extract_numbers(expected)
        actual_numbers = extract_numbers(actual)
        numeric_error: str | None = None
        if not expected_numbers or not actual_numbers:
            numeric_error = "numeric comparison found no numbers"
        elif len(expected_numbers) != len(actual_numbers):
            numeric_error = (
                f"numeric token count differs: expected {len(expected_numbers)}, actual {len(actual_numbers)}"
            )
        elif all(
            _numbers_close(exp, act, rel_tolerance, abs_tolerance)
            for exp, act in zip(expected_numbers, actual_numbers)
        ):
            return ComparisonResult(
                True,
                "numeric",
                "numeric outputs match within tolerance",
                expected_numbers,
                actual_numbers,
            )
        else:
            numeric_error = "numeric outputs differ beyond tolerance"

        if comparison == "numeric":
            return ComparisonResult(
                False,
                "numeric",
                numeric_error or "numeric comparison failed",
                expected_numbers,
                actual_numbers,
            )

    normalized_actual = normalize_text(actual)
    normalized_expected = normalize_text(expected)
    passed = normalized_actual == normalized_expected
    mode = "text" if comparison == "text" else "numeric_or_text:text"
    message = "text outputs match" if passed else "text outputs differ"
    return ComparisonResult(passed, mode, message)
