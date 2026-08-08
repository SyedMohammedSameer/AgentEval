"""How a best-of-N run picks its winning attempt.

The distinction these tests pin down is the difference between an upper bound and
a shippable number. Under `oracle` selection the hidden tests choose the winning
attempt, which is pass@k — it answers "could the agent have solved this?" and no
deployed system can reach it, because production never reveals which attempt
worked. Under `dev_tests` the agent's own visible tests choose, which is what a
real retry loop has available.

Getting this wrong does not look like a bug. It looks like a large, clean,
significant improvement from retries.
"""

from __future__ import annotations

from agenteval.environments.base import ExecResult
from agenteval.providers.base import EvalResult, Task
from agenteval.runner import _run_task


class _Env:
    """Workspace whose visible tests pass or fail on command."""

    workdir = "/tmp/fake"

    def __init__(self, dev_ok: bool):
        self.dev_ok = dev_ok
        self.torn_down = False

    def exec(self, cmd: str, timeout: float = 60.0) -> ExecResult:
        return ExecResult(stdout="", exit_code=0 if self.dev_ok else 1)

    def get_patch(self) -> str:
        return "diff --git a b"

    def repo_map(self, max_entries: int = 200) -> str:
        return ""

    def teardown(self) -> None:
        self.torn_down = True


class _Provider:
    """Scripted per-attempt outcomes: (visible_tests_pass, hidden_oracle_passes)."""

    name = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.i = 0
        self.envs = []

    def make_environment(self, task):
        env = _Env(self.script[min(self.i, len(self.script) - 1)][0])
        self.envs.append(env)
        return env

    def evaluate(self, task, patch):
        resolved = self.script[min(self.i, len(self.script) - 1)][1]
        self.i += 1
        return EvalResult(resolved=resolved, details={"reason": "tests_passed" if resolved else "tests_failed"})


class _Agent:
    def rollout(self, task, env, attempt=0):
        from agenteval.trajectory import Step, Trajectory

        t = Trajectory(task_id=task.task_id, run_name="r", model="m")
        t.add(Step(0, "", "bash", f"attempt-{attempt}", "obs"))
        t.patch = "diff --git a b"
        t.stop_reason = "submit"
        t.submitted = True
        return t


TASK = Task(task_id="t", problem_statement="fix it", dev_test_cmd="pytest -q test_basic.py")


def test_oracle_selection_keeps_retrying_until_hidden_tests_pass():
    """pass@k: the answer key drives the search."""
    provider = _Provider([(False, False), (False, False), (False, True)])
    best, attempts = _run_task(_Agent(), provider, TASK, attempts=3, selection="oracle")
    assert len(attempts) == 3
    assert best.resolved is True


def test_dev_tests_selection_stops_at_the_first_visibly_passing_attempt():
    provider = _Provider([(False, False), (True, True), (False, False)])
    best, attempts = _run_task(_Agent(), provider, TASK, attempts=3, selection="dev_tests")
    assert len(attempts) == 2          # stopped as soon as visible tests went green
    assert best.resolved is True


def test_dev_tests_selection_can_pick_a_wrong_attempt():
    """The gap that makes oracle selection an upper bound: visible tests pass,
    hidden tests do not, and a real system would ship that patch anyway."""
    provider = _Provider([(True, False), (False, True), (False, True)])
    best, attempts = _run_task(_Agent(), provider, TASK, attempts=3, selection="dev_tests")
    assert len(attempts) == 1
    assert best.resolved is False      # oracle selection would have scored this solved


def test_oracle_selection_finds_what_dev_selection_misses():
    """Same scripted rollouts, opposite outcomes — this delta is exactly the
    portion of a best-of-N gain that depends on having a perfect verifier."""
    script = [(True, False), (False, True), (False, True)]
    oracle_best, _ = _run_task(_Agent(), _Provider(script), TASK, attempts=3, selection="oracle")
    dev_best, _ = _run_task(_Agent(), _Provider(script), TASK, attempts=3, selection="dev_tests")
    assert oracle_best.resolved is True
    assert dev_best.resolved is False


def test_dev_selection_falls_back_to_the_last_attempt_when_none_pass():
    provider = _Provider([(False, False), (False, False), (False, False)])
    best, attempts = _run_task(_Agent(), provider, TASK, attempts=3, selection="dev_tests")
    assert len(attempts) == 3
    assert best.resolved is False


def test_single_attempt_is_unaffected_by_selection():
    for mode in ("oracle", "dev_tests"):
        provider = _Provider([(False, True)])
        best, attempts = _run_task(_Agent(), provider, TASK, attempts=1, selection=mode)
        assert len(attempts) == 1
        assert best.resolved is True


def test_environments_are_always_torn_down():
    provider = _Provider([(False, False), (True, True)])
    _run_task(_Agent(), provider, TASK, attempts=3, selection="dev_tests")
    assert all(e.torn_down for e in provider.envs)
