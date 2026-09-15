from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.sandbox import (
    SandboxFileContent,
    SandboxFileList,
    SandboxFileWrite,
    SandboxRunRequest,
    SandboxRunResult,
    SandboxTestResult,
    SandboxWorkspaceRead,
)
from app.services import sandbox as sandbox_service

router = APIRouter(tags=["sandbox"])


@router.post(
    "/me/projects/{user_project_id}/sandbox",
    response_model=SandboxWorkspaceRead,
)
def init_sandbox(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxWorkspaceRead:
    row = sandbox_service.ensure_workspace(db, current_user, user_project_id)
    return SandboxWorkspaceRead.model_validate(
        sandbox_service.workspace_read_payload(row, user_project_id)
    )


@router.get(
    "/me/projects/{user_project_id}/sandbox/files",
    response_model=SandboxFileList,
)
def list_sandbox_files(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxFileList:
    files = sandbox_service.list_files(db, current_user, user_project_id)
    return SandboxFileList(files=files)


@router.get(
    "/me/projects/{user_project_id}/sandbox/files/{file_path:path}",
    response_model=SandboxFileContent,
)
def read_sandbox_file(
    user_project_id: int,
    file_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxFileContent:
    return SandboxFileContent.model_validate(
        sandbox_service.read_file(db, current_user, user_project_id, file_path)
    )


@router.put(
    "/me/projects/{user_project_id}/sandbox/files/{file_path:path}",
    response_model=SandboxFileContent,
)
def write_sandbox_file(
    user_project_id: int,
    file_path: str,
    payload: SandboxFileWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxFileContent:
    return SandboxFileContent.model_validate(
        sandbox_service.write_file(
            db, current_user, user_project_id, file_path, payload.content
        )
    )


@router.delete(
    "/me/projects/{user_project_id}/sandbox/files/{file_path:path}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_sandbox_file(
    user_project_id: int,
    file_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    sandbox_service.delete_file(db, current_user, user_project_id, file_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/me/projects/{user_project_id}/sandbox/run",
    response_model=SandboxRunResult,
)
def run_sandbox(
    user_project_id: int,
    payload: SandboxRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxRunResult:
    return SandboxRunResult.model_validate(
        sandbox_service.run_command(
            db,
            current_user,
            user_project_id,
            argv=payload.argv,
            command=payload.command,
            cwd=payload.cwd,
        )
    )


@router.post(
    "/me/projects/{user_project_id}/sandbox/test",
    response_model=SandboxTestResult,
)
def test_sandbox(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxTestResult:
    return SandboxTestResult.model_validate(
        sandbox_service.run_tests(db, current_user, user_project_id)
    )
