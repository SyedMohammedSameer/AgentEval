from .base import BenchmarkProvider, EvalResult, Task
from .local import LocalProvider


def get_provider(name: str) -> BenchmarkProvider:
    if name == "local":
        return LocalProvider()
    if name == "swebench":
        from .swebench import SWEBenchProvider  # lazy: heavy optional deps
        return SWEBenchProvider()
    raise ValueError(f"unknown provider: {name!r}")


__all__ = ["BenchmarkProvider", "EvalResult", "Task", "LocalProvider", "get_provider"]
