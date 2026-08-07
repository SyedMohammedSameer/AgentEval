"""The ReAct agent loop.

Given a Task and an Environment, drive an LLM through observe->think->act until it
submits or runs out of steps. All behavioral knobs come from AgentConfig, so an
ablation is a single config field flip. Produces a Trajectory (eval is filled later).
"""

from __future__ import annotations

import hashlib
import time

from .config import AgentConfig, ModelConfig
from .environments.base import Environment
from .llm import LLMClient
from .providers.base import Task
from .tools import ParsedAction, build_system_prompt, build_task_prompt, parse_action
from .trajectory import ActionType, Step, Trajectory


class Agent:
    def __init__(
        self,
        model_cfg: ModelConfig,
        agent_cfg: AgentConfig,
        run_name: str = "run",
        seed: int = 0,
    ):
        self.model_cfg = model_cfg
        self.cfg = agent_cfg
        self.run_name = run_name
        self.seed = seed
        self.llm = LLMClient(model_cfg)

    def _rollout_seed(self, task_id: str, attempt: int) -> int:
        """A distinct, reproducible sampling seed per (run seed, task, attempt).

        Attempt number is mixed in deliberately: best-of-N is worthless if every
        attempt draws the same sample, which is exactly what a single fixed seed
        (or temperature 0) produces. Derived from a stable hash rather than
        `hash()`, which is salted per process and would break reproducibility
        across invocations.
        """
        key = f"{self.seed}:{task_id}:{attempt}".encode()
        return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")

    def rollout(self, task: Task, env: Environment, attempt: int = 0) -> Trajectory:
        """One independent attempt at the task. The runner handles best-of-N /
        pass@k by calling this multiple times with fresh environments."""
        t0 = time.monotonic()
        rollout_seed = self._rollout_seed(task.task_id, attempt)
        traj = Trajectory(
            task_id=task.task_id, run_name=self.run_name, model=self.model_cfg.model
        )

        repo_map = env.repo_map() if self.cfg.include_repo_map else None
        messages = [
            {"role": "system", "content": build_system_prompt(self.cfg.use_test_tool)},
            {"role": "user", "content": build_task_prompt(task.problem_statement, repo_map)},
        ]

        for i in range(self.cfg.max_steps):
            # Vary the seed by step as well, so a model that stalls doesn't redraw
            # the identical token sequence forever at temperature > 0.
            resp = self.llm.chat(self._context(messages), seed=rollout_seed + i)
            action = parse_action(resp.content)
            observation, done = self._execute(action, task, env)

            step = Step(
                index=i,
                thought=action.thought[:2000],
                action_type=action.type.value,
                action_input=action.input[:4000],
                observation=observation[: self.cfg.max_observation_chars],
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                latency_s=resp.latency_s,
            )
            traj.add(step)

            messages.append({"role": "assistant", "content": resp.content})

            # Loop-breaker: if the model repeats the exact same action 3x, the
            # observation clearly isn't helping — nudge it to change strategy.
            sig = (action.type.value, action.input)
            recent = [(s.action_type, s.action_input) for s in traj.steps[-3:]]
            obs_msg = f"Observation:\n{step.observation}"
            if len(recent) == 3 and all(r == sig for r in recent):
                obs_msg += (
                    "\n\n[system] You have repeated the same action 3 times with no progress. "
                    "Stop repeating it. Read the relevant source file, then EDIT it to fix the bug."
                )
            messages.append({"role": "user", "content": obs_msg})

            if done:
                traj.submitted = True
                traj.stop_reason = "submit"
                break
        else:
            traj.stop_reason = "max_steps"

        traj.patch = env.get_patch()
        if not traj.patch.strip() and traj.stop_reason == "submit":
            traj.stop_reason = "empty_patch"
        traj.wall_time_s = time.monotonic() - t0
        return traj

    def _context(self, messages: list[dict]) -> list[dict]:
        """Apply the history-construction strategy (context ablation lever)."""
        if self.cfg.history_strategy == "windowed" and len(messages) > self.cfg.history_window + 2:
            # Keep system + task prompt, then the most recent window of turns.
            head = messages[:2]
            tail = messages[-self.cfg.history_window:]
            return head + tail
        return messages

    def _execute(self, action: ParsedAction, task: Task, env: Environment) -> tuple[str, bool]:
        """Run one action, return (observation, done)."""
        if action.type == ActionType.SUBMIT:
            return "Submitting current changes.", True

        if action.type == ActionType.RUN_TESTS:
            if not self.cfg.use_test_tool:
                return "The run_tests tool is disabled. Use <bash> to inspect and fix.", False
            if not task.dev_test_cmd:
                return "No developer test command available for this task.", False
            res = env.exec(task.dev_test_cmd, timeout=120)
            return f"[test run exit={res.exit_code}]\n{res.stdout}", False

        if action.type == ActionType.BASH:
            res = env.exec(action.input, timeout=60)
            return f"[exit={res.exit_code}]\n{res.stdout}", False

        # No parseable action — nudge the model back onto protocol.
        return (
            "No action found. Respond with a thought and exactly one tag: "
            "<bash>...</bash> or <submit></submit>.",
            False,
        )
