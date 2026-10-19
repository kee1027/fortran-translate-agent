"""Dataset validation helpers for Fortran -> C++ JSON/JSONL samples."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FIELDS = (
    "id",
    "source",
    "license",
    "fortran_dialect",
    "features",
    "input_fortran",
    "output_cpp",
    "notes",
    "unsupported",
    "compile_info",
    "tests",
    "validation",
    "split",
)

VALID_DIALECTS = {"f77", "f90", "f95"}
VALID_SPLITS = {"train", "val", "test"}
VALID_COMPARISONS = {"text", "numeric", "numeric_or_text", "custom"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_non_negative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def validate_record(record: Any) -> list[str]:
    """Return a list of human-readable validation errors for one record."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record must be a JSON object"]

    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"missing required field: {field}")

    record_id = record.get("id")
    if "id" in record:
        if not _is_str(record_id):
            errors.append("id must be a non-empty string")
        elif not ID_PATTERN.fullmatch(record_id):
            errors.append("id may contain only letters, digits, '.', '_', ':', '-'")

    for field in ("source", "license", "input_fortran", "output_cpp", "notes", "split", "fortran_dialect"):
        value = record.get(field)
        if field in record and not isinstance(value, str):
            errors.append(f"{field} must be a string")
        elif field in ("source", "license") and field in record and not _is_str(value):
            errors.append(f"{field} must be a non-empty string")

    dialect = record.get("fortran_dialect")
    if dialect is not None and dialect not in VALID_DIALECTS:
        errors.append(f"fortran_dialect must be one of: {sorted(VALID_DIALECTS)}")

    split = record.get("split")
    if split is not None and split not in VALID_SPLITS:
        errors.append(f"split must be one of: {sorted(VALID_SPLITS)}")

    features = record.get("features")
    if "features" in record:
        if not isinstance(features, list) or not features:
            errors.append("features must be a non-empty list")
        elif any(not _is_str(item) for item in features):
            errors.append("features must contain non-empty strings only")
        elif len(set(features)) != len(features):
            errors.append("features must not contain duplicates")

    unsupported = record.get("unsupported")
    if "unsupported" in record:
        if not isinstance(unsupported, list):
            errors.append("unsupported must be a list")
        elif any(not isinstance(item, str) for item in unsupported):
            errors.append("unsupported must contain strings only")

    compile_info = record.get("compile_info")
    if "compile_info" in record:
        if not isinstance(compile_info, dict):
            errors.append("compile_info must be an object")
        else:
            for field in ("fortran", "cpp"):
                if not _is_str(compile_info.get(field)):
                    errors.append(f"compile_info.{field} must be a non-empty string")

    tests: Any = record.get("tests", None)
    if "tests" in record:
        if not isinstance(tests, list) or not tests:
            errors.append("tests must be a non-empty list")
        else:
            for index, test in enumerate(tests):
                prefix = f"tests[{index}]"
                if not isinstance(test, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for field in ("name", "input", "expected", "comparison"):
                    if field not in test:
                        errors.append(f"{prefix}.{field} is required")
                if "comparison" in test and test["comparison"] not in VALID_COMPARISONS:
                    errors.append(
                        f"{prefix}.comparison must be one of: {sorted(VALID_COMPARISONS)}"
                    )
                for field in ("rel_tolerance", "abs_tolerance"):
                    if field in test and not _is_non_negative_number(test[field]):
                        errors.append(f"{prefix}.{field} must be a non-negative number")

    validation = record.get("validation")
    if "validation" in record:
        if not isinstance(validation, dict):
            errors.append("validation must be an object")
        else:
            for field in ("fortran_ok", "cpp_ok", "tests_ok", "reviewed"):
                if not isinstance(validation.get(field), bool):
                    errors.append(f"validation.{field} must be a boolean")
            if validation.get("tests_ok") is True and not tests:
                errors.append("validation.tests_ok=true requires at least one test")

    return errors


def iter_records(path: Path) -> Iterable[tuple[str, Any, str | None]]:
    """Yield (label, record, parse_error) from a .jsonl file or a .json file."""
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                label = f"{path}:{line_number}"
                try:
                    yield label, json.loads(line), None
                except json.JSONDecodeError as exc:
                    yield label, None, f"JSON parse error: {exc}"
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            yield str(path), None, f"JSON parse error: {exc}"
            return
        if isinstance(payload, list):
            for index, record in enumerate(payload, start=1):
                yield f"{path}[{index}]", record, None
        else:
            yield str(path), payload, None


def validate_path(path: Path) -> tuple[int, list[str]]:
    """Validate a path and return (record_count, errors)."""
    records = list(iter_records(path))
    errors: list[str] = []
    seen_ids: set[str] = set()

    for label, record, parse_error in records:
        if parse_error:
            errors.append(f"{label}: {parse_error}")
            continue
        record_errors = validate_record(record)
        if isinstance(record, dict) and _is_str(record.get("id")):
            record_id = record["id"]
            if record_id in seen_ids:
                record_errors.append(f"duplicate id: {record_id}")
            seen_ids.add(record_id)
        errors.extend(f"{label}: {message}" for message in record_errors)

    return len(records), errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Fortran -> C++ JSON/JSONL samples.")
    parser.add_argument("paths", nargs="+", type=Path, help="JSON or JSONL files to validate")
    args = parser.parse_args(argv)

    total_records = 0
    all_errors: list[str] = []
    for path in args.paths:
        if not path.is_file():
            all_errors.append(f"{path}: file not found")
            continue
        count, errors = validate_path(path)
        total_records += count
        all_errors.extend(errors)

    if all_errors:
        print(f"INVALID: {len(all_errors)} error(s) across {total_records} record(s)")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print(f"OK: {total_records} record(s) validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

