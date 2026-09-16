"""Sandbox command runners: Docker for production, Fake for unit tests."""

from __future__ import annotations

import shlex
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings

# Learner-facing tools available in sandbox images (Node and Python).
# Keep this tight — no bash/sh/curl/wget/sudo.
ALLOWED_BINARIES = frozenset(
    {
        "node",
        "npm",
        "npx",
        "python",
        "python3",
        "pytest",
        "ls",
        "mkdir",
        "touch",
        "cat",
        "head",
        "tail",
        "pwd",
        "rm",
        "mv",
        "cp",
        "find",
        "wc",
        "echo",
        "which",
        "stat",
    }
)

# Commands that create/delete/rename files — frontend refreshes the tree after these.
FS_MUTATING_BINARIES = frozenset({"mkdir", "touch", "rm", "mv", "cp"})


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxRunner(Protocol):
    def run(
        self,
        workspace: Path,
        argv: list[str],
        *,
        cwd: str | None = None,
        image: str | None = None,
    ) -> RunResult: ...


def validate_cwd(cwd: str | None) -> str | None:
    """Normalize a workspace-relative cwd. Returns None for workspace root."""
    if cwd is None:
        return None
    cleaned = cwd.strip().replace("\\", "/")
    if not cleaned or cleaned in {".", "./", "/workspace", "workspace"}:
        return None
    cleaned = cleaned.lstrip("/")
    if cleaned.startswith("workspace/"):
        cleaned = cleaned[len("workspace/") :]
    if not cleaned or cleaned in {".", ".."}:
        return None
    parts = Path(cleaned).parts
    if ".." in parts or any(p == "" for p in parts):
        raise ValueError("cwd path traversal is not allowed")
    return Path(*parts).as_posix()


def validate_argv(argv: list[str]) -> list[str]:
    if not argv:
        raise ValueError("argv must not be empty")
    if len(argv) > 50:
        raise ValueError("argv too long")
    binary = Path(argv[0]).name
    if binary not in ALLOWED_BINARIES:
        raise ValueError(
            f"command '{binary}' is not allowed; use one of: "
            f"{', '.join(sorted(ALLOWED_BINARIES))}"
        )
    for part in argv:
        if "\x00" in part:
            raise ValueError("argv contains null bytes")
    return [binary, *argv[1:]]


def parse_command_line(command: str) -> list[str]:
    """Split a shell-like line into argv. No pipes/redirects/subshells."""
    line = command.strip()
    if not line:
        raise ValueError("command must not be empty")
    if len(line) > 4_000:
        raise ValueError("command too long")
    try:
        argv = shlex.split(line)
    except ValueError as exc:
        raise ValueError(f"could not parse command: {exc}") from exc
    if not argv:
        raise ValueError("command must not be empty")
    # Soft block shell operators so learners get a clear error instead of odd argv.
    for token in argv:
        if token in {"|", "||", "&", "&&", ";", ">", ">>", "<", "$(", "`"}:
            raise ValueError(
                "shell operators are not supported — run one allowlisted command at a time"
            )
    return validate_argv(argv)


def resolve_run_argv(
    *,
    argv: list[str] | None = None,
    command: str | None = None,
) -> list[str]:
    if argv is not None and command is not None:
        raise ValueError("provide either argv or command, not both")
    if command is not None:
        return parse_command_line(command)
    if argv is not None:
        return validate_argv(argv)
    raise ValueError("provide argv or command")


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

    def _client(self):  # noqa: ANN201 — docker.DockerClient without hard import
        import docker
        from docker.errors import DockerException

        try:
            return docker.from_env()
        except DockerException as exc:
            raise RuntimeError(
                "Cannot connect to Docker. Install/start Docker Desktop (or a Docker "
                "daemon), then build the sandbox image:\n"
                "  docker build -t socratic-sandbox-node:latest sandbox"
            ) from exc

    def run(
        self,
        workspace: Path,
        argv: list[str],
        *,
        cwd: str | None = None,
        image: str | None = None,
    ) -> RunResult:
        from docker.errors import DockerException, ImageNotFound

        safe_argv = validate_argv(argv)
        safe_cwd = validate_cwd(cwd)
        working_dir = f"/workspace/{safe_cwd}" if safe_cwd else "/workspace"
        image_name = image or self.image

        client = self._client()
        try:
            client.images.get(image_name)
        except ImageNotFound as exc:
            hint = (
                "docker build -t socratic-sandbox-python:latest -f sandbox/Dockerfile.python sandbox"
                if "python" in image_name
                else "docker build -t socratic-sandbox-node:latest sandbox"
            )
            raise RuntimeError(
                f"Sandbox image '{image_name}' not found. Build it with: {hint}"
            ) from exc
        except DockerException as exc:
            raise RuntimeError(
                "Cannot talk to Docker while checking the sandbox image. "
                "Is Docker Desktop running?"
            ) from exc

        nano_cpus = int(self.cpus * 1_000_000_000)
        container = None
        timed_out = False
        exit_code = 1
        stdout = ""
        stderr = ""
        try:
            container = client.containers.run(
                image_name,
                command=safe_argv,
                working_dir=working_dir,
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
                raw = container.logs(stdout=True, stderr=True)
                if isinstance(raw, bytes):
                    stdout = raw.decode("utf-8", errors="replace")
                else:
                    stdout = str(raw)
            except Exception:
                stdout = ""
            if timed_out and not stderr:
                stderr = (
                    f"Execution timed out after {self.timeout_sec}s "
                    "(long-running servers are stopped automatically — "
                    "use a short smoke command or Tests instead)\n"
                )
        except RuntimeError:
            raise
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
        self.calls: list[tuple[Path, list[str], str | None, str | None]] = []
        self.lock = threading.Lock()

    def run(
        self,
        workspace: Path,
        argv: list[str],
        *,
        cwd: str | None = None,
        image: str | None = None,
    ) -> RunResult:
        safe_argv = validate_argv(argv)
        safe_cwd = validate_cwd(cwd)
        with self.lock:
            self.calls.append((workspace, safe_argv, safe_cwd, image))
        return self.result


_runner_override: SandboxRunner | None = None


def get_sandbox_runner() -> SandboxRunner:
    if _runner_override is not None:
        return _runner_override
    return DockerSandboxRunner()


def set_sandbox_runner(runner: SandboxRunner | None) -> None:
    global _runner_override
    _runner_override = runner
