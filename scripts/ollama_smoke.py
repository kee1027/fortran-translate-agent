#!/usr/bin/env python3
"""Smoke-test a local Ollama model for structured Fortran -> C++ output."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = """program sum_double
  implicit none
  integer :: n, i
  real(8) :: x, total
  read(*,*) n
  total = 0.0d0
  do i = 1, n
    read(*,*) x
    total = total + x
  end do
  write(*,'(F12.6)') total
end program sum_double
"""

SYSTEM_PROMPT = """You are a careful Fortran to C++ translation assistant.
Translate Fortran 90/95 to complete, compilable C++17 code.
Use only the C++ standard library.
Preserve numerical behavior, array order, loop bounds, and input/output semantics.
Return only valid JSON with exactly these keys:
- code: the complete C++17 source code as a string
- notes: a short explanation of key mapping decisions
- unsupported: an array of unsupported Fortran features, empty if none
- confidence: one of high, medium, low
Do not wrap the JSON in Markdown and do not add commentary outside JSON.
"""


def http_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 120) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def list_models(base_url: str, timeout: int) -> list[str]:
    payload = http_json(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
    return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]


def choose_model(models: list[str], requested: str | None) -> str:
    if requested:
        return requested
    env_model = os.environ.get("OLLAMA_MODEL")
    if env_model:
        return env_model
    if not models:
        raise RuntimeError("Ollama 中没有可用模型；请先 ollama pull <model>。")
    return models[0]


def chat_once(
    base_url: str,
    model: str,
    source_code: str,
    temperature: float,
    num_predict: int,
    think: bool | None,
    timeout: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Translate the following Fortran program to C++17.\n"
                    "Return JSON only.\n\n"
                    f"```fortran\n{source_code}\n```"
                ),
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    if think is not None:
        payload["think"] = think
    return http_json(f"{base_url.rstrip('/')}/api/chat", method="POST", payload=payload, timeout=timeout)


def chat(
    base_url: str,
    model: str,
    source_code: str,
    temperature: float,
    num_predict: int,
    think: bool | None,
    timeout: int,
) -> dict[str, Any]:
    try:
        return chat_once(base_url, model, source_code, temperature, num_predict, think, timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if think is not None and exc.code == 400:
            # Older Ollama versions may not accept the "think" field.
            return chat_once(base_url, model, source_code, temperature, num_predict, None, timeout)
        raise RuntimeError(f"Ollama HTTP {exc.code}: {body}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test local Ollama structured translation.")
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--model", default=None, help="Ollama model name; defaults to OLLAMA_MODEL or first available model.")
    parser.add_argument("--source-file", type=Path, default=None, help="Fortran file to translate instead of the built-in sample.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/ollama_smoke_output.json"))
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--num-predict", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--think", action="store_true", help="Allow model thinking output when supported.")
    parser.add_argument("--no-think", action="store_true", help="Explicitly disable thinking output when supported.")
    parser.add_argument("--require-json", action="store_true", help="Exit nonzero if content is not valid JSON.")
    args = parser.parse_args(argv)

    if args.think and args.no_think:
        parser.error("--think and --no-think are mutually exclusive")
    think: bool | None = None
    if args.think:
        think = True
    elif args.no_think:
        think = False

    source_code = args.source_file.read_text(encoding="utf-8") if args.source_file else DEFAULT_SOURCE

    started = time.perf_counter()
    models = list_models(args.base_url, timeout=min(args.timeout, 30))
    model = choose_model(models, args.model)
    print(f"base_url: {args.base_url}")
    print(f"available models: {', '.join(models) if models else '(none)'}")
    print(f"using model: {model}")
    print("sending structured translation request...")

    response = chat(
        args.base_url,
        model,
        source_code,
        args.temperature,
        args.num_predict,
        think,
        args.timeout,
    )
    elapsed = time.perf_counter() - started
    message = response.get("message", {})
    content = message.get("content", "")
    thinking = message.get("thinking", "")

    parsed: Any = None
    parse_error: str | None = None
    try:
        parsed = json.loads(content)
    except Exception as exc:
        parse_error = str(exc)

    record = {
        "base_url": args.base_url,
        "model": model,
        "elapsed_seconds": round(elapsed, 3),
        "source_code": source_code,
        "response": response,
        "content": content,
        "thinking": thinking,
        "parsed": parsed,
        "parse_error": parse_error,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"elapsed: {elapsed:.2f}s")
    print(f"output: {args.output}")
    if parse_error:
        print(f"JSON parse: FAILED ({parse_error})")
        print("raw content:")
        print(content)
        return 1 if args.require_json else 0

    print("JSON parse: OK")
    if isinstance(parsed, dict):
        for key in ("confidence", "unsupported", "notes"):
            if key in parsed:
                print(f"{key}: {parsed[key]}")
        code = parsed.get("code")
        if isinstance(code, str):
            print("code preview:")
            print("\n".join(code.splitlines()[:20]))
    else:
        print("parsed JSON is not an object")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
