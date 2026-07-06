"""Action protocol + prompt construction.

The agent emits a short thought followed by exactly one action tag:

    <bash>...shell commands...</bash>
    <run_tests></run_tests>      # only if the test tool is enabled
    <submit></submit>

Tags are parsed with tolerant regexes (small models are sloppy), in priority order
submit > run_tests > bash. Everything before the tag is treated as the thought.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .trajectory import ActionType

_BASH = re.compile(r"<bash>(.*?)</bash>", re.DOTALL | re.IGNORECASE)
_TESTS = re.compile(r"<run_tests\s*/?>(?:</run_tests>)?", re.IGNORECASE)
_SUBMIT = re.compile(r"<submit\s*/?>(?:</submit>)?", re.IGNORECASE)


@dataclass
class ParsedAction:
    type: ActionType
    input: str
    thought: str


def parse_action(text: str) -> ParsedAction:
    """Extract the single action from a model turn.

    The EARLIEST tag in the text wins — that's the first action the model commits to.
    (Type-priority is wrong: a stray "then I'll <run_tests>" later in the reasoning
    must not hijack an earlier concrete <bash> command.)
    """
    candidates: list[tuple[int, ActionType, str]] = []
    m = _SUBMIT.search(text)
    if m:
        candidates.append((m.start(), ActionType.SUBMIT, ""))
    m = _TESTS.search(text)
    if m:
        candidates.append((m.start(), ActionType.RUN_TESTS, ""))
    m = _BASH.search(text)
    if m:
        candidates.append((m.start(), ActionType.BASH, m.group(1).strip()))

    if not candidates:
        return ParsedAction(ActionType.NONE, "", text.strip())

    start, atype, ainput = min(candidates, key=lambda c: c[0])
    return ParsedAction(atype, ainput, text[:start].strip())


SYSTEM_PROMPT = """You are an expert software engineer working inside a code repository via a shell.

You fix the bug described in the task by editing files, then verify your fix.

Respond every turn with a brief thought, then EXACTLY ONE action tag:

  <bash>shell command(s) to run</bash>        run commands in the repo (ls, cat, grep, python, sed...)
{tests_help}  <submit></submit>                            finish — your current file changes become the answer

Rules:
- Emit only ONE tag per turn. Do not wrap tags in markdown fences.
- To read a file: <bash>cat path/to/file.py</bash>
- To edit a file, overwrite it with a heredoc, e.g.:
  <bash>cat > path/to/file.py <<'EOF'
  ...full new file contents...
  EOF</bash>
- Make the smallest change that fixes the bug. Do not edit test files.
- When the fix is verified, use <submit></submit>.
"""

TESTS_HELP = "  <run_tests></run_tests>                      run the task's test suite and see results\n"


def build_system_prompt(use_test_tool: bool) -> str:
    return SYSTEM_PROMPT.format(tests_help=TESTS_HELP if use_test_tool else "")


def build_task_prompt(problem_statement: str, repo_map: str | None) -> str:
    parts = [f"# Task\n\n{problem_statement.strip()}\n"]
    if repo_map:
        parts.append(f"\n# Files in the repository\n\n{repo_map}\n")
    parts.append("\nBegin. Investigate first, then fix, then submit.")
    return "\n".join(parts)
