"""Thin wrapper over an OpenAI-compatible chat endpoint.

Points at a local Ollama server by default (free, offline). The same code targets
any OpenAI-compatible API by changing ModelConfig — so the harness is provider-agnostic
and dev-vs-final-model swaps are a one-line config change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from openai import OpenAI

from .config import ModelConfig


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


class LLMClient:
    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg
        self._client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.request_timeout)

    def chat(self, messages: list[dict], *, max_retries: int = 3) -> LLMResponse:
        """One chat completion. Retries transient errors with linear backoff."""
        last_err: Exception | None = None
        for attempt in range(max_retries):
            t0 = time.monotonic()
            try:
                resp = self._client.chat.completions.create(
                    model=self.cfg.model,
                    messages=messages,
                    temperature=self.cfg.temperature,
                    max_tokens=self.cfg.max_tokens,
                )
                latency = time.monotonic() - t0
                usage = resp.usage
                return LLMResponse(
                    content=resp.choices[0].message.content or "",
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    latency_s=latency,
                )
            except Exception as e:  # noqa: BLE001 — surface after retries
                last_err = e
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_err}")
