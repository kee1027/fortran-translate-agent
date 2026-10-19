#!/usr/bin/env python3
"""Compile and verify one seed sample with local tools or Docker."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.compare import compare_outputs  # noqa: E402

try:
    from scripts.validate_dataset import validate_record  # noqa: E402
except ModuleNotFoundError:  # Allows direct execution from the scripts directory.
    from validate_dataset import validate_record  # type: ignore  # noqa: E402


def run_command(
    cmd: list[str],
    cwd: Path,
    input_text: str = "",
    timeout: int = 30,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "error": None,
        }
    except FileNotFoundError:
        return {"cmd": cmd, "returncode": None, "stdout": "", "stderr": "", "error": f"command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "returncode": None, "stdout": "", "stderr": "", "error": "timeout"}
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"cmd": cmd, "returncode": None, "stdout": "", "stderr": "", "error": str(exc)}


def docker_command(
    image: str,
    workdir: Path,
    inner_cmd: list[str],
    memory: str,
    cpus: str,
) -> list[str]:
    joined = " ".join(shlex.quote(part) for part in inner_cmd)
    host_dir = str(workdir.resolve())
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--memory",
        memory,
        "--cpus",
        cpus,
        "-v",
        f"{host_dir}:/work",
        "-w",
        "/work",
        image,
        "bash",
        "-lc",
        joined,
    ]


def execute_in_engine(
    engine: str,
    inner_cmd: list[str],
    workdir: Path,
    input_text: str,
    timeout: int,
    image: str,
    memory: str,
    cpus: str,
) -> dict[str, Any]:
    if engine == "docker":
        cmd = docker_command(image, workdir, inner_cmd, memory, cpus)
        return run_command(cmd, cwd=workdir, input_text=input_text, timeout=timeout)
    return run_command(inner_cmd, cwd=workdir, input_text=input_text, timeout=timeout)


def build_commands(dialect: str) -> dict[str, list[str]]:
    fortran_std = "-std=legacy" if dialect == "f77" else "-std=f2008"
    return {
        "fortran": ["gfortran", fortran_std, "-O0", "-Wall", "-Wextra", "-fcheck=all", "main.f90", "-o", "main_f"],
        "cpp": ["g++", "-std=c++17", "-O0", "-Wall", "-Wextra", "main.cpp", "-o", "main_cpp"],
    }


def verify_sample(
    sample_dir: Path,
    engine: str,
    image: str,
    timeout: int,
    memory: str,
    cpus: str,
    dry_run: bool,
) -> dict[str, Any]:
    metadata_path = sample_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    record_errors = validate_record(metadata)
    if record_errors:
        raise ValueError("invalid metadata: " + "; ".join(record_errors))

    commands = build_commands(metadata["fortran_dialect"])
    result: dict[str, Any] = {
        "id": metadata["id"],
        "sample_dir": str(sample_dir),
        "engine": engine,
        "commands": commands,
        "compile": {},
        "tests": [],
    }

    with tempfile.TemporaryDirectory(prefix="f2cpp-seed-") as raw_tmp:
        workdir = Path(raw_tmp)
        (workdir / "main.f90").write_text(metadata["input_fortran"], encoding="utf-8")
        (workdir / "main.cpp").write_text(metadata["output_cpp"], encoding="utf-8")

        if dry_run:
            result["dry_run"] = True
            return result

        for language in ("fortran", "cpp"):
            compile_result = execute_in_engine(
                engine,
                commands[language],
                workdir,
                "",
                timeout,
                image,
                memory,
                cpus,
            )
            result["compile"][language] = compile_result
            if compile_result.get("returncode") != 0:
                return result

        all_passed = True
        for test in metadata["tests"]:
            input_text = test.get("input", "")
            reference = execute_in_engine(
                engine,
                ["./main_f"],
                workdir,
                input_text,
                timeout,
                image,
                memory,
                cpus,
            )
            candidate = execute_in_engine(
                engine,
                ["./main_cpp"],
                workdir,
                input_text,
                timeout,
                image,
                memory,
                cpus,
            )
            comparison = compare_outputs(
                candidate.get("stdout", ""),
                test.get("expected", ""),
                comparison=test.get("comparison", "numeric_or_text"),
                rel_tolerance=float(test.get("rel_tolerance", 1.0e-9)),
                abs_tolerance=float(test.get("abs_tolerance", 1.0e-12)),
            )
            reference_comparison = compare_outputs(
                reference.get("stdout", ""),
                test.get("expected", ""),
                comparison=test.get("comparison", "numeric_or_text"),
                rel_tolerance=float(test.get("rel_tolerance", 1.0e-9)),
                abs_tolerance=float(test.get("abs_tolerance", 1.0e-12)),
            )
            passed = (
                reference.get("returncode") == 0
                and candidate.get("returncode") == 0
                and reference_comparison.passed
                and comparison.passed
            )
            all_passed = all_passed and passed
            result["tests"].append(
                {
                    "name": test["name"],
                    "passed": passed,
                    "reference": reference,
                    "candidate": candidate,
                    "reference_comparison": reference_comparison.__dict__,
                    "candidate_comparison": comparison.__dict__,
                }
            )

        result["validation"] = {
            "fortran_ok": result["compile"].get("fortran", {}).get("returncode") == 0,
            "cpp_ok": result["compile"].get("cpp", {}).get("returncode") == 0,
            "tests_ok": all_passed,
            "reviewed": False,
        }
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile and verify one seed sample.")
    parser.add_argument("sample_dir", type=Path)
    parser.add_argument("--engine", choices=["local", "docker"], default="local")
    parser.add_argument("--image", default="gcc:13")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--memory", default="512m")
    parser.add_argument("--cpus", default="1")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update-metadata", action="store_true")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.sample_dir.is_dir():
        parser.error(f"sample_dir not found: {args.sample_dir}")

    try:
        result = verify_sample(
            args.sample_dir,
            args.engine,
            args.image,
            args.timeout,
            args.memory,
            args.cpus,
            args.dry_run,
        )
    except Exception as exc:
        print(f"FAILED: {exc}")
        return 1

    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    validation = result.get("validation", {})
    if args.update_metadata and validation:
        metadata_path = args.sample_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["validation"] = validation
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if validation.get("tests_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

