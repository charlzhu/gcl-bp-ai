#!/usr/bin/env python3
"""受控 Codex Runner。

职责：读取 TASK 目录下的 prompt，调用 codex exec，实时打印输出并写入 event.jsonl。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from event_bus import append_event, print_event

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_prompt(task_dir: Path, prompt_file: str) -> str:
    """读取 Codex prompt。"""
    path = task_dir / prompt_file
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt file: {path}")
    return path.read_text(encoding="utf-8")


def normalize_codex_line(line: str) -> str:
    """尽量把 Codex --json 输出转成人能看的消息；解析失败则原样返回。"""
    text = line.strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text

    # 兼容不同版本 Codex JSONL 字段。
    for key in ("message", "content", "text", "summary", "type"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(data, ensure_ascii=False)


def run_codex(task_id: str, task_dir: Path, project_root: Path, prompt_file: str, model: str | None = None) -> int:
    """调用 codex exec，并同步日志。"""
    if shutil.which("codex") is None:
        msg = "未找到 codex 命令，请先安装并登录 Codex CLI。"
        append_event(task_dir, task_id, "codex", "precheck", msg, level="error")
        print_event("codex", "precheck", msg, level="error")
        return 127

    prompt = load_prompt(task_dir, prompt_file)
    stdout_log = task_dir / "codex_stdout.log"
    stderr_log = task_dir / "codex_stderr.log"
    final_file = task_dir / "codex_final.md"

    cmd = [
        "codex",
        "exec",
        "--cd",
        str(project_root),
        "--sandbox",
        "workspace-write",
        "--json",
        "--output-last-message",
        str(final_file),
        "-",
    ]
    if model:
        cmd.extend(["--model", model])

    append_event(task_dir, task_id, "codex", "start", f"开始调用 Codex CLI，prompt={prompt_file}")
    print_event("codex", "start", f"开始调用 Codex CLI，prompt={prompt_file}")

    with stdout_log.open("a", encoding="utf-8") as out, stderr_log.open("a", encoding="utf-8") as err:
        process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert process.stdin is not None
        process.stdin.write(prompt)
        process.stdin.close()

        assert process.stdout is not None
        for line in process.stdout:
            out.write(line)
            out.flush()
            message = normalize_codex_line(line)
            if message:
                print_event("codex", "running", message)
                append_event(task_dir, task_id, "codex", "running", message)

        assert process.stderr is not None
        stderr_text = process.stderr.read()
        if stderr_text:
            err.write(stderr_text)
            err.flush()
            print_event("codex", "stderr", stderr_text.strip(), level="warn")
            append_event(task_dir, task_id, "codex", "stderr", stderr_text.strip(), level="warn")

        return_code = process.wait()

    if return_code == 0:
        append_event(task_dir, task_id, "codex", "done", "Codex 执行完成")
        print_event("codex", "done", "Codex 执行完成")
    else:
        append_event(task_dir, task_id, "codex", "failed", f"Codex 执行失败，退出码：{return_code}", level="error")
        print_event("codex", "failed", f"Codex 执行失败，退出码：{return_code}", level="error")
    return return_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--prompt-file", default="codex_prompt.md")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    return run_codex(
        task_id=args.task_id,
        task_dir=Path(args.task_dir),
        project_root=Path(args.project_root),
        prompt_file=args.prompt_file,
        model=args.model,
    )


if __name__ == "__main__":
    sys.exit(main())
