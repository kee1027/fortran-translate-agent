#!/usr/bin/env python3
"""Audit the A800 training environment for a 7B LoRA workflow.

The script intentionally uses only the Python standard library for its own
imports. PyTorch and training packages are imported inside probes so the audit
can still produce a useful report on a partially configured machine.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def run_command(cmd: list[str], timeout: int = 20) -> dict[str, Any]:
    """Run a command and capture a JSON-friendly result."""
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {"cmd": cmd, "found": False, "returncode": None, "stdout": "", "stderr": "", "error": "command not found"}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "found": True, "returncode": None, "stdout": "", "stderr": "", "error": "timeout"}
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"cmd": cmd, "found": True, "returncode": None, "stdout": "", "stderr": "", "error": str(exc)}

    return {
        "cmd": cmd,
        "found": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "error": None,
    }


def collect_nvidia_smi() -> dict[str, Any]:
    query = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.free,driver_version,compute_cap",
        "--format=csv,noheader,nounits",
    ]
    result = run_command(query)
    gpus: list[dict[str, Any]] = []
    if result.get("found") and result.get("returncode") == 0:
        for line in result.get("stdout", "").splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 6:
                gpus.append(
                    {
                        "index": parts[0],
                        "name": parts[1],
                        "memory_total_mib": int(parts[2]) if parts[2].isdigit() else parts[2],
                        "memory_free_mib": int(parts[3]) if parts[3].isdigit() else parts[3],
                        "driver_version": parts[4],
                        "compute_cap": parts[5],
                    }
                )
    return {"command": result, "gpus": gpus, "gpu_count": len(gpus)}


def collect_torch(run_gpu_smoke: bool) -> dict[str, Any]:
    report: dict[str, Any] = {"installed": False}
    try:
        import torch  # type: ignore
    except Exception as exc:
        report["import_error"] = str(exc)
        return report

    report["installed"] = True
    report["version"] = getattr(torch, "__version__", None)
    report["cuda_version"] = getattr(getattr(torch, "version", None), "cuda", None)
    report["cuda_available"] = bool(torch.cuda.is_available())
    report["device_count"] = int(torch.cuda.device_count()) if report["cuda_available"] else 0
    report["devices"] = []
    report["bf16_supported"] = None

    if report["cuda_available"]:
        for index in range(report["device_count"]):
            props = torch.cuda.get_device_properties(index)
            report["devices"].append(
                {
                    "index": index,
                    "name": props.name,
                    "total_memory_gib": round(props.total_memory / (1024**3), 2),
                    "major": props.major,
                    "minor": props.minor,
                    "multi_processor_count": props.multi_processor_count,
                }
            )
        try:
            report["bf16_supported"] = bool(torch.cuda.is_bf16_supported())
        except Exception as exc:
            report["bf16_supported_error"] = str(exc)

    if run_gpu_smoke and report["cuda_available"]:
        try:
            device = torch.device("cuda:0")
            dtype = torch.bfloat16 if report.get("bf16_supported") else torch.float16
            left = torch.randn(1024, 1024, device=device, dtype=dtype)
            right = torch.randn(1024, 1024, device=device, dtype=dtype)
            torch.cuda.synchronize()
            started = time.perf_counter()
            result = left @ right
            torch.cuda.synchronize()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            report["gpu_smoke"] = {
                "ok": True,
                "dtype": str(dtype),
                "shape": list(result.shape),
                "elapsed_ms": round(elapsed_ms, 3),
            }
            del left, right, result
            torch.cuda.empty_cache()
        except Exception as exc:
            report["gpu_smoke"] = {"ok": False, "error": str(exc)}

    return report


def collect_packages() -> dict[str, Any]:
    names = [
        "transformers",
        "peft",
        "trl",
        "accelerate",
        "datasets",
        "bitsandbytes",
        "deepspeed",
        "flash_attn",
        "safetensors",
        "sentencepiece",
        "huggingface_hub",
        "yaml",
    ]
    report: dict[str, Any] = {}
    for name in names:
        try:
            module = importlib.import_module(name)
            report[name] = {
                "installed": True,
                "version": getattr(module, "__version__", "unknown"),
            }
        except Exception as exc:
            report[name] = {"installed": False, "error": str(exc)}
    return report


def collect_disk(paths: list[str]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        try:
            usage = shutil.disk_usage(path)
            report[str(path)] = {
                "exists": path.exists(),
                "total_gib": round(usage.total / (1024**3), 2),
                "used_gib": round(usage.used / (1024**3), 2),
                "free_gib": round(usage.free / (1024**3), 2),
            }
        except Exception as exc:
            report[str(path)] = {"exists": path.exists(), "error": str(exc)}
    return report


def build_recommendations(report: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    torch_report = report.get("torch", {})
    packages = report.get("packages", {})
    nvidia = report.get("nvidia_smi", {})

    if not torch_report.get("installed"):
        recommendations.append("PyTorch 未安装或当前 Python 无法导入 torch。")
    else:
        if not torch_report.get("cuda_available"):
            recommendations.append("PyTorch 无法访问 CUDA；请检查驱动、CUDA 容器和 torch+cu121 安装。")
        if torch_report.get("device_count", 0) < 2:
            recommendations.append("当前 PyTorch 可见 GPU 少于 2 张；单卡 7B LoRA 可继续，但双卡实验需要排查。")
        if torch_report.get("bf16_supported") is False:
            recommendations.append("当前 GPU 不支持 bf16 矩阵运算；请确认是否使用 A800 及正确的 torch 版本。")

    gpu_count = nvidia.get("gpu_count", 0)
    if gpu_count and gpu_count < 2:
        recommendations.append("nvidia-smi 可见 GPU 少于 2 张，请确认两张 A800 都在同一训练环境内。")
    if not gpu_count and not torch_report.get("cuda_available"):
        recommendations.append("未检测到可用 NVIDIA GPU；正式训练不能在该环境执行。")

    for package in ("transformers", "peft", "accelerate", "datasets", "safetensors"):
        if not packages.get(package, {}).get("installed"):
            recommendations.append(f"缺少训练基础包：{package}。")
    if not packages.get("trl", {}).get("installed"):
        recommendations.append("未安装 trl；若使用 LLaMA-Factory 或自定义 SFT 脚本，需要补齐。")
    if not packages.get("bitsandbytes", {}).get("installed"):
        recommendations.append("未安装 bitsandbytes；MVP 的 7B bf16 LoRA 不阻塞，14B/30B QLoRA 需要。")
    if not packages.get("flash_attn", {}).get("installed"):
        recommendations.append("未安装 flash-attn；先不要把它设为硬依赖，7B LoRA 可先不使用。")

    for path, info in report.get("disk", {}).items():
        free = info.get("free_gib")
        if isinstance(free, (int, float)) and free < 100:
            recommendations.append(f"磁盘 {path} 可用空间不足 100 GiB，可能不够存放模型、数据和 checkpoint。")

    return recommendations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit an A800 environment for 7B LoRA fine-tuning.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/a800_env_report.json"))
    parser.add_argument("--disk-path", action="append", default=["."], help="Path to report disk usage for; repeatable.")
    parser.add_argument("--gpu-smoke", action="store_true", help="Run a small bf16/FP16 GPU matmul smoke test.")
    args = parser.parse_args(argv)

    report: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "cwd": os.getcwd(),
        "optional_env": {
            key: os.environ.get(key)
            for key in (
                "CUDA_VISIBLE_DEVICES",
                "HF_HOME",
                "HUGGINGFACE_HUB_CACHE",
                "TRANSFORMERS_CACHE",
                "PYTORCH_CUDA_ALLOC_CONF",
            )
        },
        "nvidia_smi": collect_nvidia_smi(),
        "nvcc": run_command(["nvcc", "-V"]),
        "torch": collect_torch(args.gpu_smoke),
        "packages": collect_packages(),
        "disk": collect_disk(args.disk_path),
    }
    report["recommendations"] = build_recommendations(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"report: {args.output}")
    nvidia = report["nvidia_smi"]
    print(f"nvidia-smi GPUs: {nvidia.get('gpu_count', 0)}")
    for gpu in nvidia.get("gpus", []):
        print(f"  - GPU {gpu['index']}: {gpu['name']} {gpu['memory_total_mib']} MiB, free {gpu['memory_free_mib']} MiB")
    torch_report = report["torch"]
    if torch_report.get("installed"):
        print(
            "torch:",
            torch_report.get("version"),
            "cuda:",
            torch_report.get("cuda_version"),
            "available:",
            torch_report.get("cuda_available"),
            "devices:",
            torch_report.get("device_count"),
            "bf16:",
            torch_report.get("bf16_supported"),
        )
    else:
        print("torch: not installed or not importable")

    print("recommendations:")
    for item in report["recommendations"]:
        print(f"  - {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
