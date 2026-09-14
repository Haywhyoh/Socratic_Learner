from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SandboxWorkspaceRead(BaseModel):
    id: int
    user_project_id: int
    status: str
    last_run_at: datetime | None = None
    last_test_summary: dict[str, Any] | list[Any] | None = None
    workspace_path: str

    model_config = {"from_attributes": True}


class SandboxFileEntry(BaseModel):
    path: str
    is_dir: bool
    size: int | None = None


class SandboxFileList(BaseModel):
    files: list[SandboxFileEntry]


class SandboxFileContent(BaseModel):
    path: str
    content: str


class SandboxFileWrite(BaseModel):
    content: str = Field(..., max_length=1_000_000)


class SandboxRunRequest(BaseModel):
    argv: list[str] = Field(..., min_length=1, max_length=50)


class SandboxRunResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    argv: list[str]


class SandboxTestResult(BaseModel):
    passed: int = 0
    failed: int = 0
    errors: int = 0
    exit_code: int
    timed_out: bool = False
    output: str
    summary: str
    outcome: str
