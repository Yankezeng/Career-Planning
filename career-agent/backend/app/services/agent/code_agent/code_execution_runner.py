from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.core.project_paths import PROJECT_ROOT


class _HTMLTagValidator(HTMLParser):
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = str(tag or "").strip().lower()
        if lowered and lowered not in self.VOID_TAGS:
            self.stack.append(lowered)

    def handle_endtag(self, tag: str) -> None:
        lowered = str(tag or "").strip().lower()
        if not lowered:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{lowered}>.")
            return
        if self.stack[-1] == lowered:
            self.stack.pop()
            return
        if lowered in self.stack:
            while self.stack and self.stack[-1] != lowered:
                missing = self.stack.pop()
                self.errors.append(f"Missing closing tag for <{missing}>.")
            if self.stack and self.stack[-1] == lowered:
                self.stack.pop()
            return
        self.errors.append(f"Unexpected closing tag </{lowered}>.")

    def finalize(self) -> list[str]:
        for item in reversed(self.stack):
            self.errors.append(f"Missing closing tag for <{item}>.")
        return self.errors


@dataclass
class RunnerLimits:
    max_files: int = 12
    max_file_size: int = 200_000
    max_total_size: int = 800_000
    compile_timeout_sec: int = 60
    test_timeout_sec: int = 60
    max_output_chars: int = 8_000


class CodeExecutionRunner:
    LANGUAGE_ALIASES: dict[str, str] = {
        "python": "python",
        "py": "python",
        "c": "c",
        "c++": "cpp",
        "cpp": "cpp",
        "cc": "cpp",
        "cxx": "cpp",
        "javascript": "javascript",
        "js": "javascript",
        "node": "javascript",
        "html": "html",
        "css": "css",
        "vue": "vue",
        "vbs": "vbs",
        "vbscript": "vbs",
        "mermaid": "mermaid",
        "mermain": "mermaid",
    }

    EXTENSIONS: dict[str, set[str]] = {
        "python": {".py"},
        "c": {".c"},
        "cpp": {".cpp", ".cc", ".cxx"},
        "javascript": {".js", ".mjs", ".cjs"},
        "html": {".html", ".htm"},
        "css": {".css"},
        "vue": {".vue"},
        "vbs": {".vbs"},
        "mermaid": {".mmd", ".mermaid", ".md"},
    }

    NETWORK_PATTERNS: dict[str, tuple[str, ...]] = {
        "python": (
            "import socket",
            "from socket",
            "import requests",
            "urllib.request",
            "http.client",
            "aiohttp",
            "websocket",
        ),
        "javascript": (
            "fetch(",
            "axios",
            "require('http')",
            'require("http")',
            "require('https')",
            'require("https")',
            "xmlhttprequest",
            "websocket",
        ),
        "c": (
            "winsock",
            "sys/socket",
            "winhttp",
            "libcurl",
            "wsastartup",
        ),
        "cpp": (
            "winsock",
            "sys/socket",
            "winhttp",
            "libcurl",
            "wsastartup",
        ),
        "vbs": (
            "msxml2.xmlhttp",
            "winhttp.winhttprequest",
            "internetexplorer.application",
            "adodb.stream",
        ),
    }

    MERMAID_ROOT_TYPES = (
        "graph",
        "flowchart",
        "sequencediagram",
        "classdiagram",
        "statediagram",
        "statediagram-v2",
        "erdiagram",
        "journey",
        "gantt",
        "pie",
        "mindmap",
        "timeline",
        "gitgraph",
        "quadrantchart",
        "requirementdiagram",
        "c4context",
    )

    def __init__(self, limits: RunnerLimits | None = None) -> None:
        self.limits = limits or RunnerLimits()

    @classmethod
    def normalize_language(cls, language: str | None) -> str:
        token = str(language or "").strip().lower()
        return cls.LANGUAGE_ALIASES.get(token, token)

    def verify(
        self,
        *,
        language: str,
        files: list[dict[str, Any]] | None,
        tests: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized = self.normalize_language(language)
        if normalized not in self.EXTENSIONS:
            return self._failure_report(
                language=normalized,
                reason=f"Unsupported language: {language}",
            )

        prepared_files = self._sanitize_files(files=files or [], language=normalized)
        if prepared_files.get("error"):
            return self._failure_report(language=normalized, reason=str(prepared_files["error"]))

        clean_files = prepared_files["files"]
        clean_tests = self._sanitize_supporting_files(
            files=tests or [],
            prefix="tests",
        )

        network_block = self._detect_network_usage(language=normalized, files=clean_files, tests=clean_tests)
        if network_block:
            return self._failure_report(language=normalized, reason=network_block, checks=[{"name": "network_guard", "passed": False}])

        with tempfile.TemporaryDirectory(prefix="code-agent-run-") as tmp:
            tmp_dir = Path(tmp)
            write_result = self._write_files(root=tmp_dir, files=clean_files, tests=clean_tests)
            if write_result.get("error"):
                return self._failure_report(language=normalized, reason=str(write_result["error"]))

            compile_report = self._run_compile_stage(language=normalized, root=tmp_dir, files=clean_files)
            test_report = self._run_test_stage(
                language=normalized,
                root=tmp_dir,
                files=clean_files,
                tests=clean_tests,
                compile_report=compile_report,
            )

        checks = [
            {"name": "compile_or_syntax", "passed": bool(compile_report.get("passed")), "summary": compile_report.get("summary") or ""},
            {"name": "self_test", "passed": bool(test_report.get("passed")), "summary": test_report.get("summary") or ""},
        ]
        passed = bool(compile_report.get("passed")) and bool(test_report.get("passed"))
        report = {
            "ok": passed,
            "language": normalized,
            "compile": compile_report,
            "tests": test_report,
            "checks": checks,
            "required_checks": ["compile_or_syntax", "self_test"],
            "blocked": not passed,
        }
        if not passed:
            report["failure_reason"] = test_report.get("summary") if not test_report.get("passed") else compile_report.get("summary")
        return report

    def has_c_compiler(self) -> bool:
        return bool(self._resolve_cl_command())

    def _sanitize_files(self, *, files: list[dict[str, Any]], language: str) -> dict[str, Any]:
        if not files:
            return {"error": "No code files were generated."}

        if len(files) > self.limits.max_files:
            return {"error": f"Too many files: {len(files)} > {self.limits.max_files}."}

        allowed_ext = self.EXTENSIONS.get(language) or set()
        total_size = 0
        clean: list[dict[str, str]] = []

        for row in files:
            path_text = self._safe_relative_path(str((row or {}).get("path") or ""))
            content = str((row or {}).get("content") or "")
            if not path_text:
                return {"error": "File path is empty or unsafe."}
            suffix = Path(path_text).suffix.lower()
            if allowed_ext and suffix not in allowed_ext:
                return {"error": f"Invalid file extension for {language}: {path_text}"}
            if len(content.encode("utf-8")) > self.limits.max_file_size:
                return {"error": f"File too large: {path_text}"}
            total_size += len(content.encode("utf-8"))
            clean.append({"path": path_text, "content": content})

        if total_size > self.limits.max_total_size:
            return {"error": "Total generated code size exceeds limit."}
        return {"files": clean}

    def _sanitize_supporting_files(self, *, files: list[dict[str, Any]], prefix: str) -> list[dict[str, str]]:
        clean: list[dict[str, str]] = []
        for row in files:
            path_text = self._safe_relative_path(str((row or {}).get("path") or ""))
            content = str((row or {}).get("content") or "")
            if not path_text or not content:
                continue
            if not path_text.startswith(f"{prefix}/"):
                path_text = f"{prefix}/{Path(path_text).name}"
            clean.append({"path": path_text, "content": content})
        return clean[: self.limits.max_files]

    @staticmethod
    def _safe_relative_path(value: str) -> str:
        text = str(value or "").strip().replace("\\", "/")
        if not text or text.startswith("/") or ":" in text:
            return ""
        if any(part in {"..", ""} for part in text.split("/")):
            return ""
        return text

    def _write_files(self, *, root: Path, files: list[dict[str, str]], tests: list[dict[str, str]]) -> dict[str, Any]:
        try:
            for row in [*files, *tests]:
                target = root / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(row["content"], encoding="utf-8")
            return {"ok": True}
        except Exception as exc:
            return {"error": str(exc)}
    def _run_compile_stage(self, *, language: str, root: Path, files: list[dict[str, str]]) -> dict[str, Any]:
        if language == "python":
            command = [sys.executable, "-m", "py_compile", *[item["path"] for item in files]]
            return self._command_stage(name="python_compile", command=command, root=root, timeout=self.limits.compile_timeout_sec)

        if language == "javascript":
            entry = self._pick_entry(files=files, language=language)
            if not entry:
                return {"passed": False, "summary": "No JavaScript entry file found."}
            command = ["node", "--check", entry]
            return self._command_stage(name="node_check", command=command, root=root, timeout=self.limits.compile_timeout_sec)

        if language == "vbs":
            entry = self._pick_entry(files=files, language=language)
            if not entry:
                return {"passed": False, "summary": "No VBS entry file found."}
            command = ["cscript", "//nologo", entry]
            return self._command_stage(name="vbs_check", command=command, root=root, timeout=self.limits.compile_timeout_sec)

        if language in {"c", "cpp"}:
            return self._compile_c_family(language=language, root=root, files=files)

        if language == "html":
            return self._validate_html(files=files)

        if language == "css":
            return self._validate_css(files=files)

        if language == "vue":
            return self._validate_vue(root=root, files=files)

        if language == "mermaid":
            return self._validate_mermaid(files=files)

        return {"passed": False, "summary": f"Unsupported compile stage for {language}."}

    def _run_test_stage(
        self,
        *,
        language: str,
        root: Path,
        files: list[dict[str, str]],
        tests: list[dict[str, str]],
        compile_report: dict[str, Any],
    ) -> dict[str, Any]:
        if not compile_report.get("passed"):
            return {"passed": False, "summary": "Compile or syntax validation failed; self-test skipped."}

        if language == "python":
            return self._test_python(root=root, tests=tests)
        if language == "javascript":
            return self._test_javascript(root=root, files=files, tests=tests)
        if language in {"c", "cpp"}:
            return self._test_binary(root=root)
        if language == "vbs":
            return self._test_vbs(root=root, files=files, tests=tests)
        if language in {"html", "css", "vue", "mermaid"}:
            return {"passed": True, "summary": "Syntax and structure checks passed."}
        return {"passed": False, "summary": "Unsupported test stage."}

    def _test_python(self, *, root: Path, tests: list[dict[str, str]]) -> dict[str, Any]:
        test_path = self._pick_test_file(tests=tests, suffix=".py")
        if not test_path:
            return {"passed": False, "summary": "Python self-test script is required but missing."}
        runner = (
            "import runpy, sys; "
            "sys.path.insert(0, '.'); "
            f"runpy.run_path(r'{test_path}', run_name='__main__')"
        )
        command = [sys.executable, "-c", runner]
        return self._command_stage(name="python_test", command=command, root=root, timeout=self.limits.test_timeout_sec)

    def _test_javascript(self, *, root: Path, files: list[dict[str, str]], tests: list[dict[str, str]]) -> dict[str, Any]:
        test_path = self._pick_test_file(tests=tests, suffix=".js")
        if test_path:
            return self._command_stage(name="node_test", command=["node", test_path], root=root, timeout=self.limits.test_timeout_sec)
        entry = self._pick_entry(files=files, language="javascript")
        if not entry:
            return {"passed": False, "summary": "No JavaScript entry file found for smoke test."}
        return self._command_stage(name="node_smoke", command=["node", entry], root=root, timeout=self.limits.test_timeout_sec)

    def _test_vbs(self, *, root: Path, files: list[dict[str, str]], tests: list[dict[str, str]]) -> dict[str, Any]:
        test_path = self._pick_test_file(tests=tests, suffix=".vbs")
        if test_path:
            return self._command_stage(
                name="vbs_test",
                command=["cscript", "//nologo", test_path],
                root=root,
                timeout=self.limits.test_timeout_sec,
            )
        entry = self._pick_entry(files=files, language="vbs")
        if not entry:
            return {"passed": False, "summary": "No VBS entry file found for smoke test."}
        return self._command_stage(
            name="vbs_smoke",
            command=["cscript", "//nologo", entry],
            root=root,
            timeout=self.limits.test_timeout_sec,
        )

    def _compile_c_family(self, *, language: str, root: Path, files: list[dict[str, str]]) -> dict[str, Any]:
        entry = self._pick_entry(files=files, language=language)
        if not entry:
            return {"passed": False, "summary": f"No {language} entry file found."}

        command_info = self._resolve_cl_command()
        if not command_info:
            return {"passed": False, "summary": "MSVC compiler (cl) is unavailable in current environment."}

        exe_name = "program.exe"
        source = str((root / entry).resolve())
        exe_path = str((root / exe_name).resolve())
        language_flag = "/TP /EHsc" if language == "cpp" else "/TC"

        if command_info["mode"] == "direct":
            command = [
                "cl",
                "/nologo",
                *language_flag.split(),
                source,
                f"/Fe:{exe_path}",
            ]
        else:
            vcvars = command_info["vcvars_path"]
            batch_file = root / "compile_with_msvc.bat"
            batch_file.write_text(
                "\n".join(
                    [
                        "@echo off",
                        f'call "{vcvars}" >nul',
                        f'cl /nologo {language_flag} "{source}" /Fe:"{exe_path}"',
                    ]
                ),
                encoding="utf-8",
            )
            command = ["cmd", "/d", "/c", str(batch_file)]

        report = self._command_stage(name=f"{language}_compile", command=command, root=root, timeout=self.limits.compile_timeout_sec)
        report["binary_path"] = exe_name if report.get("passed") else ""
        return report

    def _test_binary(self, *, root: Path) -> dict[str, Any]:
        executable = root / "program.exe"
        if not executable.exists():
            return {"passed": False, "summary": "Compiled binary was not generated."}
        return self._command_stage(
            name="binary_smoke",
            command=[str(executable)],
            root=root,
            timeout=self.limits.test_timeout_sec,
        )

    def _validate_html(self, *, files: list[dict[str, str]]) -> dict[str, Any]:
        entry = self._pick_entry(files=files, language="html")
        if not entry:
            return {"passed": False, "summary": "No HTML file found."}
        content = self._content_by_path(files=files, path=entry)
        parser = _HTMLTagValidator()
        try:
            parser.feed(content)
            parser.close()
        except Exception as exc:
            return {"passed": False, "summary": f"HTML parse failed: {exc}"}
        errors = parser.finalize()
        has_html = bool(re.search(r"<html[\s>]", content, flags=re.IGNORECASE))
        has_body = bool(re.search(r"<body[\s>]", content, flags=re.IGNORECASE))
        if errors:
            return {"passed": False, "summary": "; ".join(errors[:4])}
        if not (has_html and has_body):
            return {"passed": False, "summary": "HTML document must include <html> and <body> structure."}
        return {"passed": True, "summary": "HTML syntax and structure checks passed."}

    def _validate_css(self, *, files: list[dict[str, str]]) -> dict[str, Any]:
        entry = self._pick_entry(files=files, language="css")
        if not entry:
            return {"passed": False, "summary": "No CSS file found."}
        content = self._content_by_path(files=files, path=entry)
        brace = 0
        for char in content:
            if char == "{":
                brace += 1
            elif char == "}":
                brace -= 1
            if brace < 0:
                return {"passed": False, "summary": "CSS braces are unbalanced."}
        if brace != 0:
            return {"passed": False, "summary": "CSS braces are unbalanced."}
        if ":" not in content or ";" not in content:
            return {"passed": False, "summary": "CSS must contain declarations with ':' and ';'."}
        return {"passed": True, "summary": "CSS syntax checks passed."}

    def _validate_vue(self, *, root: Path, files: list[dict[str, str]]) -> dict[str, Any]:
        entry = self._pick_entry(files=files, language="vue")
        if not entry:
            return {"passed": False, "summary": "No Vue SFC file found."}
        content = self._content_by_path(files=files, path=entry)
        has_template = bool(re.search(r"<template[\s>]", content, flags=re.IGNORECASE))
        has_script = bool(re.search(r"<script[\s>]", content, flags=re.IGNORECASE))
        if not has_template:
            return {"passed": False, "summary": "Vue SFC must include a <template> block."}
        if not has_script:
            return {"passed": False, "summary": "Vue SFC must include a <script> block."}

        template_match = re.search(r"<template[^>]*>(.*?)</template>", content, flags=re.IGNORECASE | re.DOTALL)
        if template_match:
            html_report = self._validate_html(files=[{"path": "index.html", "content": f"<html><body>{template_match.group(1)}</body></html>"}])
            if not html_report.get("passed"):
                return {"passed": False, "summary": f"Vue template invalid: {html_report.get('summary')}"}

        compiler = self._resolve_vue_compiler()
        if not compiler:
            return {"passed": False, "summary": "Vue compiler not found; strict verification failed."}

        validator_script = root / "vue_validate.cjs"
        validator_script.write_text(
            (
                "const fs = require('fs');\n"
                "const path = process.argv[2];\n"
                "const source = fs.readFileSync(path, 'utf8');\n"
                "const compiler = require(process.argv[3]);\n"
                "const parsed = compiler.parse(source);\n"
                "if (parsed.errors && parsed.errors.length) {\n"
                "  console.error(parsed.errors.map((e) => (e.message || String(e))).join('\\n'));\n"
                "  process.exit(2);\n"
                "}\n"
                "if (parsed.descriptor && parsed.descriptor.template) {\n"
                "  const templateResult = compiler.compileTemplate({ source: parsed.descriptor.template.content, id: 'code-agent' });\n"
                "  if (templateResult.errors && templateResult.errors.length) {\n"
                "    console.error(templateResult.errors.map((e) => (e.message || String(e))).join('\\n'));\n"
                "    process.exit(3);\n"
                "  }\n"
                "}\n"
                "process.exit(0);\n"
            ),
            encoding="utf-8",
        )
        report = self._command_stage(
            name="vue_compile",
            command=["node", str(validator_script), entry, compiler],
            root=root,
            timeout=self.limits.compile_timeout_sec,
        )
        if report.get("passed"):
            report["summary"] = "Vue SFC parser and compiler checks passed."
        return report

    def _validate_mermaid(self, *, files: list[dict[str, str]]) -> dict[str, Any]:
        entry = self._pick_entry(files=files, language="mermaid")
        if not entry:
            return {"passed": False, "summary": "No Mermaid file found."}
        content = self._content_by_path(files=files, path=entry).strip()
        if not content:
            return {"passed": False, "summary": "Mermaid content is empty."}

        first_line = ""
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("%%"):
                first_line = line
                break
        if not first_line:
            return {"passed": False, "summary": "Mermaid diagram must contain a root declaration."}

        root_token = first_line.split()[0].lower()
        if root_token not in self.MERMAID_ROOT_TYPES:
            return {"passed": False, "summary": f"Unsupported Mermaid root type: {root_token}"}

        if root_token in {"graph", "flowchart"} and not re.search(r"-->|---|\-\.\-|==>", content):
            return {"passed": False, "summary": "Flowchart Mermaid should contain at least one edge."}

        if root_token == "sequencediagram" and "participant" not in content.lower():
            return {"passed": False, "summary": "Sequence Mermaid should declare participants."}

        return {"passed": True, "summary": "Mermaid syntax checks passed."}
    def _pick_entry(self, *, files: list[dict[str, str]], language: str) -> str:
        if not files:
            return ""
        preferred = {
            "python": ("main.py",),
            "javascript": ("main.js", "index.js", "app.js"),
            "c": ("main.c",),
            "cpp": ("main.cpp",),
            "html": ("index.html",),
            "css": ("style.css", "main.css"),
            "vue": ("App.vue", "main.vue"),
            "vbs": ("main.vbs",),
            "mermaid": ("diagram.mmd", "diagram.mermaid"),
        }.get(language, ())
        candidate_paths = [item["path"] for item in files]
        lowered_map = {item.lower(): item for item in candidate_paths}
        for name in preferred:
            if name.lower() in lowered_map:
                return lowered_map[name.lower()]
        return candidate_paths[0]

    @staticmethod
    def _content_by_path(*, files: list[dict[str, str]], path: str) -> str:
        for item in files:
            if item["path"] == path:
                return item["content"]
        return ""

    @staticmethod
    def _pick_test_file(*, tests: list[dict[str, str]], suffix: str) -> str:
        for item in tests:
            if item["path"].lower().endswith(suffix.lower()):
                return item["path"]
        return ""

    def _detect_network_usage(self, *, language: str, files: list[dict[str, str]], tests: list[dict[str, str]]) -> str:
        patterns = self.NETWORK_PATTERNS.get(language) or ()
        if not patterns:
            return ""
        joined = "\n".join([*(item["content"] for item in files), *(item["content"] for item in tests)]).lower()
        for token in patterns:
            if token.lower() in joined:
                return f"Network capability detected and blocked by policy: {token}"
        return ""

    def _command_stage(self, *, name: str, command: list[str], root: Path, timeout: int) -> dict[str, Any]:
        result = self._run_command(command=command, root=root, timeout=timeout)
        return {
            "name": name,
            "passed": bool(result["passed"]),
            "summary": result["summary"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result.get("exit_code"),
            "timed_out": result.get("timed_out", False),
            "command": " ".join(command),
        }

    def _run_command(self, *, command: list[str], root: Path, timeout: int) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                command,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            stdout = self._truncate_output(completed.stdout)
            stderr = self._truncate_output(completed.stderr)
            passed = completed.returncode == 0
            summary = "Command succeeded." if passed else f"Command failed with exit code {completed.returncode}."
            return {
                "passed": passed,
                "summary": summary,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": completed.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            stdout = self._truncate_output(str(exc.stdout or ""))
            stderr = self._truncate_output(str(exc.stderr or ""))
            return {
                "passed": False,
                "summary": f"Command timed out after {timeout} seconds.",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": None,
                "timed_out": True,
            }
        except FileNotFoundError:
            return {
                "passed": False,
                "summary": f"Command not found: {command[0]}",
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "timed_out": False,
            }
        except Exception as exc:
            return {
                "passed": False,
                "summary": f"Command execution error: {exc}",
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "timed_out": False,
            }

    def _truncate_output(self, value: str) -> str:
        text = str(value or "")
        limit = self.limits.max_output_chars
        if len(text) <= limit:
            return text
        return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"

    def _resolve_cl_command(self) -> dict[str, str] | None:
        direct = shutil.which("cl")
        if direct:
            return {"mode": "direct"}

        vcvars = self._locate_vcvars64()
        if vcvars:
            return {"mode": "vcvars", "vcvars_path": vcvars}
        return None

    def _locate_vcvars64(self) -> str:
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if not vswhere.exists():
            return ""
        try:
            result = subprocess.run(
                [
                    str(vswhere),
                    "-latest",
                    "-products",
                    "*",
                    "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                    "-property",
                    "installationPath",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            install_path = str(result.stdout or "").strip()
            if not install_path:
                return ""
            candidate = Path(install_path) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
            if candidate.exists():
                return str(candidate)
        except Exception:
            return ""
        return ""

    @staticmethod
    def _resolve_vue_compiler() -> str:
        cwd = Path.cwd()
        project_root = PROJECT_ROOT
        candidates = [
            project_root / "frontend" / "node_modules" / "@vue" / "compiler-sfc" / "dist" / "compiler-sfc.cjs.js",
            project_root / "backend" / "node_modules" / "@vue" / "compiler-sfc" / "dist" / "compiler-sfc.cjs.js",
            cwd / "frontend" / "node_modules" / "@vue" / "compiler-sfc" / "dist" / "compiler-sfc.cjs.js",
            cwd / "node_modules" / "@vue" / "compiler-sfc" / "dist" / "compiler-sfc.cjs.js",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return ""

    @staticmethod
    def _failure_report(*, language: str, reason: str, checks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {
            "ok": False,
            "language": language,
            "compile": {"passed": False, "summary": reason},
            "tests": {"passed": False, "summary": "Verification aborted."},
            "checks": checks or [
                {"name": "compile_or_syntax", "passed": False, "summary": reason},
                {"name": "self_test", "passed": False, "summary": "Verification aborted."},
            ],
            "required_checks": ["compile_or_syntax", "self_test"],
            "blocked": True,
            "failure_reason": reason,
        }

    @staticmethod
    def build_verification_summary(report: dict[str, Any]) -> str:
        if report.get("ok"):
            return "All required verification checks passed."
        reasons = [
            str((report.get("compile") or {}).get("summary") or "").strip(),
            str((report.get("tests") or {}).get("summary") or "").strip(),
            str(report.get("failure_reason") or "").strip(),
        ]
        reasons = [item for item in reasons if item]
        return reasons[0] if reasons else "Verification failed."

    @staticmethod
    def parse_model_output(payload: str) -> dict[str, Any]:
        raw = str(payload or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        fenced_json = re.findall(r"```json\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
        for block in fenced_json:
            try:
                data = json.loads(block.strip())
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue

        files: list[dict[str, str]] = []
        matches = re.findall(r"```([\w#+.-]*)\n(.*?)```", raw, flags=re.DOTALL)
        for lang, code in matches:
            language = str(lang or "").strip().lower()
            path = {
                "python": "main.py",
                "py": "main.py",
                "javascript": "main.js",
                "js": "main.js",
                "c": "main.c",
                "cpp": "main.cpp",
                "c++": "main.cpp",
                "html": "index.html",
                "css": "style.css",
                "vue": "App.vue",
                "vbs": "main.vbs",
                "vbscript": "main.vbs",
                "mermaid": "diagram.mmd",
                "mmd": "diagram.mmd",
            }.get(language, "main.txt")
            files.append({"path": path, "content": code.strip()})
        if files:
            return {"files": files}
        return {}
