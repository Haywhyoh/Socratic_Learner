from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from app.core.config import settings

app = typer.Typer(help="Socratic Learner CLI — talk to the backend without a frontend.")
auth_app = typer.Typer(help="Authentication commands")
app.add_typer(auth_app, name="auth")

console = Console()
TOKEN_PATH = Path.home() / ".socratic" / "token"


def _base_url() -> str:
    return settings.api_base_url.rstrip("/")


def _save_token(token: str) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token.strip(), encoding="utf-8")


def _load_token() -> str | None:
    if not TOKEN_PATH.exists():
        return None
    token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    return token or None


def _headers() -> dict[str, str]:
    token = _load_token()
    if not token:
        console.print("[red]Not logged in. Run: socratic auth login[/red]")
        raise typer.Exit(code=1)
    return {"Authorization": f"Bearer {token}"}


def _client() -> httpx.Client:
    return httpx.Client(base_url=_base_url(), timeout=30.0)


def _print_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


@auth_app.command("register")
def auth_register(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, confirmation_prompt=True, hide_input=True),
) -> None:
    with _client() as client:
        response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    console.print("[green]Registered successfully.[/green]")
    _print_json(response.json())


@auth_app.command("login")
def auth_login(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
) -> None:
    with _client() as client:
        response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    token = response.json()["access_token"]
    _save_token(token)
    console.print(f"[green]Logged in. Token saved to {TOKEN_PATH}[/green]")


@app.command("courses")
def list_courses() -> None:
    with _client() as client:
        response = client.get("/api/v1/courses")
    response.raise_for_status()
    table = Table("ID", "Name", "Primary", "Secondary")
    for course in response.json():
        table.add_row(
            str(course["id"]),
            course["name"],
            course["primary_label"],
            course["secondary_label"],
        )
    console.print(table)


@app.command("options")
def list_options(
    course_id: Annotated[int, typer.Argument(help="Course ID")],
    parent_id: Annotated[
        Optional[int],
        typer.Option(help="Primary option ID for secondary options"),
    ] = None,
) -> None:
    # Direct Python calls (e.g. from `socratic start`) must use a real None default;
    # typer.Option(...) as a default leaves an OptionInfo object instead.
    if not isinstance(parent_id, int):
        parent_id = None
    with _client() as client:
        if parent_id is None:
            response = client.get(f"/api/v1/courses/{course_id}/options")
        else:
            response = client.get(f"/api/v1/courses/{course_id}/options/{parent_id}/options")
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    table = Table("ID", "Name", "Slug", "Parent")
    for option in response.json():
        table.add_row(
            str(option["id"]),
            option["name"],
            option["slug"],
            str(option["parent_id"] or "-"),
        )
    console.print(table)


@app.command("enroll")
def enroll(
    course: int = typer.Option(..., help="Course ID"),
    primary: int = typer.Option(..., help="Primary option ID"),
    secondary: int = typer.Option(..., help="Secondary option ID"),
    mode: str = typer.Option(..., help="project or concept"),
) -> None:
    if mode not in {"project", "concept"}:
        console.print("[red]mode must be 'project' or 'concept'[/red]")
        raise typer.Exit(code=1)
    with _client() as client:
        response = client.post(
            "/api/v1/enrollments",
            headers=_headers(),
            json={
                "course_id": course,
                "primary_option_id": primary,
                "secondary_option_id": secondary,
                "learning_mode": mode,
            },
        )
        if response.status_code == 409 and "already exists" in response.text:
            console.print(
                "[yellow]Already enrolled on this path — opening your existing enrollment.[/yellow]"
            )
            enrollments = client.get("/api/v1/enrollments", headers=_headers()).json()
            match = next(
                (
                    e
                    for e in enrollments
                    if e["course_id"] == course
                    and e["primary_option_id"] == primary
                    and e["secondary_option_id"] == secondary
                    and e["learning_mode"] == mode
                ),
                None,
            )
            if match is None:
                console.print(f"[red]{response.status_code}: {response.text}[/red]")
                raise typer.Exit(code=1)
            detail = client.get(f"/api/v1/enrollments/{match['id']}", headers=_headers())
            detail.raise_for_status()
            _print_enrollment(detail.json())
            return
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    console.print("[green]Enrolled.[/green]")
    _print_enrollment(response.json())


def _print_enrollment(data: dict[str, Any]) -> None:
    console.print(
        f"[bold]Enrollment {data['id']}[/bold] — "
        f"{(data.get('course') or {}).get('name')} / "
        f"{(data.get('primary_option') or {}).get('name')} / "
        f"{(data.get('secondary_option') or {}).get('name')} / "
        f"{data['learning_mode']}"
    )
    if data.get("user_project"):
        up = data["user_project"]
        project = up.get("project") or data.get("assigned_project") or {}
        console.print(
            f"Project: {project.get('title', up['project_id'])} "
            f"(user_project={up['id']}, status={up['status']})"
        )
        for um in data.get("user_milestones", []):
            milestone = um.get("milestone") or {}
            console.print(
                f"  \\[{um['status']}] user_milestone={um['id']} "
                f"#{milestone.get('order_index')} {milestone.get('title')}"
            )
        console.print(
            "[dim]Complete next: socratic milestone complete <user_milestone_id>\n"
            "Restart from a milestone (also resets later ones): "
            "socratic milestone restart <user_milestone_id>[/dim]"
        )
    if data.get("concept_session_id"):
        console.print(f"Concept session id={data['concept_session_id']}")
        console.print("[dim]View question with: socratic concept show[/dim]")


@app.command("path")
def show_path() -> None:
    with _client() as client:
        response = client.get("/api/v1/enrollments", headers=_headers())
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    enrollments = response.json()
    if not enrollments:
        console.print("[yellow]No enrollments yet.[/yellow]")
        return
    console.print(f"[bold]{len(enrollments)} enrollment(s)[/bold]")
    with _client() as client:
        for item in enrollments:
            detail = client.get(f"/api/v1/enrollments/{item['id']}", headers=_headers())
            detail.raise_for_status()
            _print_enrollment(detail.json())
            console.print("")


@app.command("milestone")
def milestone_action(
    action: str = typer.Argument(..., help="'complete' or 'restart'"),
    user_milestone_id: int = typer.Argument(..., help="User milestone ID"),
) -> None:
    if action not in {"complete", "restart"}:
        console.print(
            "[red]Use: socratic milestone complete <id>  or  "
            "socratic milestone restart <id>[/red]"
        )
        raise typer.Exit(code=1)
    with _client() as client:
        response = client.post(
            f"/api/v1/me/milestones/{user_milestone_id}/{action}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    if action == "complete":
        console.print("[green]Milestone completed.[/green]")
    else:
        console.print(
            "[green]Milestone restarted "
            "(this milestone and any later ones are pending again).[/green]"
        )
    _print_json(response.json())


@app.command("concept")
def concept_show(
    action: Annotated[str, typer.Argument(help="Use 'show'")] = "show",
    session_id: Annotated[
        Optional[int],
        typer.Option(help="Concept session ID"),
    ] = None,
) -> None:
    if action != "show":
        console.print("[red]Only 'show' is supported[/red]")
        raise typer.Exit(code=1)
    if not isinstance(session_id, int):
        session_id = None
    if session_id is None:
        with _client() as client:
            enrollments = client.get("/api/v1/enrollments", headers=_headers()).json()
        session_id = next(
            (e["concept_session_id"] for e in reversed(enrollments) if e.get("concept_session_id")),
            None,
        )
        if session_id is None:
            console.print("[yellow]No concept session found.[/yellow]")
            raise typer.Exit(code=1)
    with _client() as client:
        response = client.get(f"/api/v1/concept-sessions/{session_id}", headers=_headers())
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    data = response.json()
    console.print(f"Session {data['id']} status={data['status']}")
    if data["question_text"]:
        console.print(f"\n[bold]Question[/bold]\n{data['question_text']}\n")
        console.print("[dim]Question came from the seeded catalog (AI generation later).[/dim]")
    else:
        console.print("question=None")
        console.print(
            "[dim]No question on this session. Re-run `python -m app.seed` to backfill, "
            "or enroll concept on Django for a fresh seeded question.[/dim]"
        )


@app.command("start")
def interactive_start() -> None:
    """Walk through register/login → course → options → mode interactively."""
    console.print("[bold]Socratic Learner — interactive start[/bold]")
    console.print(
        "[dim]Tip: enter the ID from the left column of each table "
        "(FastAPI is usually 5, not 1).[/dim]"
    )
    if _load_token() is None:
        if typer.confirm("No saved token. Register a new account?", default=True):
            email = typer.prompt("Email")
            password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
            auth_register(email=email, password=password)
        email = typer.prompt("Login email")
        password = typer.prompt("Password", hide_input=True)
        auth_login(email=email, password=password)

    list_courses()
    course_id = typer.prompt("Course ID (left column)", type=int)
    list_options(course_id=course_id)
    primary_id = typer.prompt("Primary option ID — e.g. Python (left column)", type=int)
    list_options(course_id=course_id, parent_id=primary_id)
    secondary_id = typer.prompt(
        "Secondary option ID — e.g. FastAPI/Django (left column, NOT the parent id)",
        type=int,
    )
    mode = typer.prompt("Learning mode (project/concept)", default="project")
    enroll(course=course_id, primary=primary_id, secondary=secondary_id, mode=mode)


if __name__ == "__main__":
    app()
