"""Sandbox command runners: Docker for production, Fake for unit tests."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings

ALLOWED_BINARIES = frozenset({"python", "python3", "pytest"})


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxRunner(Protocol):
    def run(self, workspace: Path, argv: list[str]) -> RunResult: ...


def validate_argv(argv: list[str]) -> list[str]:
    if not argv:
        raise ValueError("argv must not be empty")
    if len(argv) > 50:
        raise ValueError("argv too long")
    binary = Path(argv[0]).name
    if binary not in ALLOWED_BINARIES:
        raise ValueError(
            f"command '{binary}' is not allowed; use one of: {', '.join(sorted(ALLOWED_BINARIES))}"
        )
    for part in argv:
        if "\x00" in part:
            raise ValueError("argv contains null bytes")
    return [binary, *argv[1:]]


class DockerSandboxRunner:
    """Ephemeral container: mount workspace, run allowlisted argv, remove."""

    def __init__(
        self,
        *,
        image: str | None = None,
        memory_mb: int | None = None,
        cpus: float | None = None,
        timeout_sec: int | None = None,
        pids_limit: int | None = None,
    ) -> None:
        self.image = image or settings.sandbox_image
        self.memory_mb = memory_mb if memory_mb is not None else settings.sandbox_memory_mb
        self.cpus = cpus if cpus is not None else settings.sandbox_cpus
        self.timeout_sec = (
            timeout_sec if timeout_sec is not None else settings.sandbox_timeout_sec
        )
        self.pids_limit = (
            pids_limit if pids_limit is not None else settings.sandbox_pids_limit
        )

    def run(self, workspace: Path, argv: list[str]) -> RunResult:
        import docker
        from docker.errors import ImageNotFound

        safe_argv = validate_argv(argv)
        client = docker.from_env()
        try:
            client.images.get(self.image)
        except ImageNotFound as exc:
            raise RuntimeError(
                f"Sandbox image '{self.image}' not found. "
                "Build it with: docker build -t socratic-sandbox-python:latest "
                "backend/sandbox"
            ) from exc

        nano_cpus = int(self.cpus * 1_000_000_000)
        container = None
        timed_out = False
        exit_code = 1
        stdout = ""
        stderr = ""
        try:
            container = client.containers.run(
                self.image,
                command=safe_argv,
                working_dir="/workspace",
                volumes={str(workspace.resolve()): {"bind": "/workspace", "mode": "rw"}},
                network_mode="none",
                mem_limit=f"{self.memory_mb}m",
                nano_cpus=nano_cpus,
                pids_limit=self.pids_limit,
                user="1000:1000",
                detach=True,
                stdout=True,
                stderr=True,
            )
            try:
                result = container.wait(timeout=self.timeout_sec)
                exit_code = int(result.get("StatusCode", 1))
            except Exception:
                timed_out = True
                exit_code = 124
                try:
                    container.kill()
                except Exception:
                    pass
            try:
                raw = container.logs(stdout=True, stderr=True, demux=True)
                if isinstance(raw, tuple):
                    out_b, err_b = raw
                    stdout = (out_b or b"").decode("utf-8", errors="replace")
                    stderr = (err_b or b"").decode("utf-8", errors="replace")
                else:
                    stdout = (
                        raw.decode("utf-8", errors="replace")
                        if isinstance(raw, bytes)
                        else str(raw)
                    )
            except Exception:
                pass
            if timed_out and not stderr:
                stderr = f"Execution timed out after {self.timeout_sec}s\n"
        except Exception as exc:
            raise RuntimeError(f"Failed to start sandbox container: {exc}") from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

        return RunResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
        )


class FakeSandboxRunner:
    """Deterministic runner for unit tests — never executes learner code."""

    def __init__(self, result: RunResult | None = None) -> None:
        self.result = result or RunResult(exit_code=0, stdout="", stderr="")
        self.calls: list[tuple[Path, list[str]]] = []
        self.lock = threading.Lock()

    def run(self, workspace: Path, argv: list[str]) -> RunResult:
        safe_argv = validate_argv(argv)
        with self.lock:
            self.calls.append((workspace, safe_argv))
        return self.result


_runner_override: SandboxRunner | None = None


def get_sandbox_runner() -> SandboxRunner:
    if _runner_override is not None:
        return _runner_override
    return DockerSandboxRunner()


def set_sandbox_runner(runner: SandboxRunner | None) -> None:
    global _runner_override
    _runner_override = runner
