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


def _print_milestones_table(
    user_milestones: list[dict[str, Any]],
    *,
    project_title: str | None = None,
    project_status: str | None = None,
    user_project_id: int | None = None,
) -> None:
    header_bits = []
    if project_title:
        header_bits.append(project_title)
    if user_project_id is not None:
        header_bits.append(f"user_project={user_project_id}")
    if project_status:
        header_bits.append(f"status={project_status}")
    if header_bits:
        console.print("[bold]" + " · ".join(header_bits) + "[/bold]")

    table = Table("User milestone ID", "#", "Title", "Status", "Completed at")
    ordered = sorted(
        user_milestones,
        key=lambda um: (um.get("milestone") or {}).get("order_index") or 0,
    )
    for um in ordered:
        milestone = um.get("milestone") or {}
        completed = um.get("completed_at") or "-"
        table.add_row(
            str(um["id"]),
            str(milestone.get("order_index", "-")),
            str(milestone.get("title", "-")),
            str(um.get("status", "-")),
            str(completed),
        )
    console.print(table)
    console.print(
        "[dim]Complete next: socratic milestone complete <user_milestone_id>\n"
        "Restart from a milestone (also resets later ones): "
        "socratic milestone restart <user_milestone_id>\n"
        "Full definition: socratic brief[/dim]"
    )


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
        if project.get("description"):
            console.print(f"[italic]{project['description']}[/italic]")
        milestones = data.get("user_milestones") or up.get("user_milestones") or []
        _print_milestones_table(
            milestones,
            project_title=project.get("title"),
            project_status=up.get("status"),
            user_project_id=up.get("id"),
        )
    if data.get("concept_session_id"):
        console.print(f"Concept session id={data['concept_session_id']}")
        console.print("[dim]View question with: socratic concept show[/dim]")


def _print_list_section(title: str, items: list[Any] | None) -> None:
    if not items:
        return
    console.print(f"\n[bold]{title}[/bold]")
    for item in items:
        console.print(f"  • {item}")


def _print_project_brief(project: dict[str, Any], milestones: list[dict[str, Any]] | None = None) -> None:
    console.print(f"[bold]{project.get('title')}[/bold] (project_id={project.get('id')})")
    if project.get("description"):
        console.print(f"\n[bold]Summary[/bold]\n{project['description']}")
    if project.get("difficulty"):
        console.print(f"\n[bold]Difficulty[/bold]\n{project['difficulty']}")
    if project.get("objective"):
        console.print(f"\n[bold]Objective[/bold]\n{project['objective']}")
    _print_list_section("Prerequisites", project.get("prerequisites"))
    if project.get("expected_outcome"):
        console.print(f"\n[bold]Expected outcome[/bold]\n{project['expected_outcome']}")
    _print_list_section("Skills", project.get("skills"))
    _print_list_section("Concepts", project.get("concepts"))
    _print_list_section("Constraints", project.get("constraints"))
    _print_list_section("Tests", project.get("tests"))
    _print_list_section("Evaluation criteria", project.get("evaluation_criteria"))
    _print_list_section("Extension challenges", project.get("extension_challenges"))
    resources = project.get("recommended_resources") or []
    if resources:
        console.print("\n[bold]Recommended resources[/bold]")
        for resource in resources:
            title = resource.get("title") if isinstance(resource, dict) else str(resource)
            url = resource.get("url") if isinstance(resource, dict) else ""
            if url:
                console.print(f"  • {title} — {url}")
            else:
                console.print(f"  • {title}")
    items = milestones if milestones is not None else project.get("milestones") or []
    if not items:
        return
    console.print("\n[bold]Milestones[/bold]")
    ordered = sorted(items, key=lambda m: m.get("order_index") or 0)
    for milestone in ordered:
        console.print(
            f"\n[bold]#{milestone.get('order_index')} {milestone.get('title')}[/bold]"
        )
        if milestone.get("description"):
            console.print(milestone["description"])
        if milestone.get("instructions"):
            console.print(f"\n[cyan]Instructions[/cyan]\n{milestone['instructions']}")
        if milestone.get("success_criteria"):
            console.print(
                f"\n[green]Success criteria[/green]\n{milestone['success_criteria']}"
            )


@app.command("brief")
def show_brief(
    project_id: Annotated[
        Optional[int],
        typer.Option(help="Project ID (defaults to your latest project enrollment)"),
    ] = None,
) -> None:
    """Show the full project definition and detailed milestone instructions."""
    if not isinstance(project_id, int):
        project_id = None
    with _client() as client:
        if project_id is None:
            enrollments = client.get("/api/v1/enrollments", headers=_headers())
            if enrollments.status_code >= 400:
                console.print(f"[red]{enrollments.status_code}: {enrollments.text}[/red]")
                raise typer.Exit(code=1)
            project_id = next(
                (
                    e["assigned_project_id"]
                    for e in reversed(enrollments.json())
                    if e.get("assigned_project_id")
                ),
                None,
            )
            if project_id is None:
                console.print(
                    "[yellow]No project enrollment found. "
                    "Pass --project-id or enroll in project mode first.[/yellow]"
                )
                raise typer.Exit(code=1)
        response = client.get(f"/api/v1/projects/{project_id}")
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    _print_project_brief(response.json())


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
        data = response.json()
        if action == "complete":
            console.print("[green]Milestone completed.[/green]")
            # Fetch full project progress for a table view
            project = client.get(
                f"/api/v1/me/projects/{data['user_project_id']}",
                headers=_headers(),
            )
            project.raise_for_status()
            body = project.json()
            project_info = body.get("project") or {}
            _print_milestones_table(
                body.get("user_milestones") or [],
                project_title=project_info.get("title"),
                project_status=body.get("status"),
                user_project_id=body.get("id"),
            )
        else:
            console.print(
                "[green]Milestone restarted "
                "(this milestone and any later ones are pending again).[/green]"
            )
            project_info = data.get("project") or {}
            _print_milestones_table(
                data.get("user_milestones") or [],
                project_title=project_info.get("title"),
                project_status=data.get("status"),
                user_project_id=data.get("id"),
            )


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
