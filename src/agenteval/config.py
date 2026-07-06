"""Configuration objects for models, agents, and experiment runs.

Everything an ablation might vary lives on ``AgentConfig`` so a single field flip
(e.g. ``use_test_tool=False``) defines a clean experimental condition.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field


@dataclass
class ModelConfig:
    """Which model to call and how. Provider-agnostic via an OpenAI-compatible API.

    Defaults point at a local Ollama server so runs are free. Swap ``base_url`` /
    ``api_key`` / ``model`` to target any OpenAI-compatible endpoint later.
    """

    model: str = "qwen2.5-coder:7b"
    base_url: str = field(default_factory=lambda: os.environ.get("AGENTEVAL_BASE_URL", "http://localhost:11434/v1"))
    api_key: str = field(default_factory=lambda: os.environ.get("AGENTEVAL_API_KEY", "ollama"))
    temperature: float = 0.0
    max_tokens: int = 2048
    # Wall-clock ceiling per single model call, seconds.
    request_timeout: float = 180.0

    def label(self) -> str:
        return self.model.replace(":", "-").replace("/", "-")


@dataclass
class AgentConfig:
    """The agent's behavior. These are the levers ablations sweep over."""

    # --- loop budget ---
    max_steps: int = 20
    # --- tool availability (ablation lever) ---
    use_test_tool: bool = True          # expose a `run_tests` action to the agent
    # --- context construction (ablation lever) ---
    include_repo_map: bool = True       # prepend a file listing of the workspace
    max_observation_chars: int = 4000   # truncate long command output fed back to model
    history_strategy: str = "full"      # "full" | "windowed" — how much history to keep
    history_window: int = 12            # steps kept when history_strategy == "windowed"
    # --- self-verification / retry (ablation lever) ---
    self_check: bool = True             # let the agent inspect test output before submitting
    attempts: int = 1                   # best-of-N independent attempts (pass@k style)


@dataclass
class RunConfig:
    """A full experiment: a named condition = model + agent + which tasks."""

    name: str = "baseline"
    provider: str = "local"             # "local" | "swebench"
    subset: str = "smoke"               # provider-specific subset identifier
    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    seed: int = 0
    output_dir: str = "results"

    def to_dict(self) -> dict:
        return asdict(self)
