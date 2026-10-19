#!/usr/bin/env python3
"""Convert the project's JSON/JSONL samples into LLaMA-Factory ShareGPT JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.validate_dataset import iter_records, validate_record
except ModuleNotFoundError:  # Allows direct execution: python scripts/convert_to_llamafactory.py
    from validate_dataset import iter_records, validate_record


INSTRUCTION = """You are a careful Fortran to C++ translation assistant.
Translate the following Fortran 90/95 code to complete, compilable C++17.
Use only the C++ standard library unless the sample says otherwise.
Preserve numerical behavior, array order, loop bounds, and input/output semantics.
Return only a JSON object with keys: code, notes, unsupported, confidence.
"""


def assistant_target(record: dict[str, Any]) -> str:
    validation = record.get("validation", {})
    confidence = "high" if all(
        validation.get(key) is True for key in ("fortran_ok", "cpp_ok", "tests_ok")
    ) else "low"
    payload = {
        "code": record["output_cpp"],
        "notes": record.get("notes", ""),
        "unsupported": record.get("unsupported", []),
        "confidence": confidence,
    }
    return json.dumps(payload, ensure_ascii=False)


def convert_record(record: dict[str, Any]) -> dict[str, Any]:
    user_content = (
        f"{INSTRUCTION}\n"
        "Translate this Fortran code:\n"
        "```fortran\n"
        f"{record['input_fortran']}\n"
        "```"
    )
    return {
        "id": record["id"],
        "messages": [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_target(record)},
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert project samples to LLaMA-Factory ShareGPT JSONL.")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/llamafactory/fortran_cpp_train.jsonl"))
    parser.add_argument("--dataset-name", default="fortran_cpp_train")
    parser.add_argument("--dataset-info", type=Path, default=Path("data/llamafactory/dataset_info.json"))
    parser.add_argument("--no-dataset-info", action="store_true")
    args = parser.parse_args(argv)

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in args.inputs:
        if not path.is_file():
            errors.append(f"{path}: file not found")
            continue
        for label, record, parse_error in iter_records(path):
            if parse_error:
                errors.append(f"{label}: {parse_error}")
                continue
            record_errors = validate_record(record)
            if record_errors:
                errors.extend(f"{label}: {message}" for message in record_errors)
                continue
            records.append(record)

    if errors:
        print(f"CONVERSION FAILED: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(convert_record(record), ensure_ascii=False) + "\n")

    print(f"wrote {len(records)} record(s) to {args.output}")

    if not args.no_dataset_info:
        args.dataset_info.parent.mkdir(parents=True, exist_ok=True)
        info = {
            args.dataset_name: {
                "file_name": args.output.name,
                "formatting": "sharegpt",
                "columns": {"messages": "messages"},
                "tags": {
                    "role_tag": "role",
                    "content_tag": "content",
                    "user_tag": "user",
                    "assistant_tag": "assistant",
                },
            }
        }
        args.dataset_info.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote dataset info to {args.dataset_info}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


