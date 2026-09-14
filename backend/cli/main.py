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
sandbox_app = typer.Typer(help="Sandboxed Python workspace (Docker)")
app.add_typer(auth_app, name="auth")
app.add_typer(sandbox_app, name="sandbox")

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


def _print_http_error(response: httpx.Response) -> None:
    detail: Any = None
    try:
        body = response.json()
        detail = body.get("detail", body)
    except Exception:
        detail = response.text
    if isinstance(detail, list):
        detail = "; ".join(str(item) for item in detail)
    console.print(f"[red]{response.status_code}: {detail}[/red]")


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
        "Full definition: socratic brief\n"
        "Coach: socratic coach start  ·  socratic coach message  ·  socratic state  ·  socratic hint[/dim]"
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


def _latest_user_project_id(client: httpx.Client) -> int:
    enrollments = client.get("/api/v1/enrollments", headers=_headers())
    if enrollments.status_code >= 400:
        console.print(f"[red]{enrollments.status_code}: {enrollments.text}[/red]")
        raise typer.Exit(code=1)
    user_project_id = next(
        (
            (e.get("user_project") or {}).get("id")
            for e in reversed(enrollments.json())
            if (e.get("user_project") or {}).get("id")
        ),
        None,
    )
    if user_project_id is None:
        console.print("[yellow]No project enrollment found.[/yellow]")
        raise typer.Exit(code=1)
    return int(user_project_id)


def _latest_user_milestone_id(client: httpx.Client, user_project_id: int) -> int:
    project = client.get(f"/api/v1/me/projects/{user_project_id}", headers=_headers())
    if project.status_code >= 400:
        console.print(f"[red]{project.status_code}: {project.text}[/red]")
        raise typer.Exit(code=1)
    pending = [
        um
        for um in project.json().get("user_milestones") or []
        if um.get("status") == "pending"
    ]
    pending.sort(key=lambda um: (um.get("milestone") or {}).get("order_index") or 0)
    if not pending:
        console.print("[yellow]No pending milestone.[/yellow]")
        raise typer.Exit(code=1)
    return int(pending[0]["id"])


def _print_cards(cards: list[dict[str, Any]]) -> None:
    if not cards:
        console.print("[dim]No concept cards for this milestone.[/dim]")
        return
    for card in cards:
        console.print(f"\n[bold]{card.get('name')}[/bold] (card_id={card.get('id')})")
        if card.get("why_it_matters"):
            console.print(card["why_it_matters"])
        if card.get("explanation"):
            console.print(f"[dim]{card['explanation']}[/dim]")
        questions = card.get("research_questions") or []
        if questions:
            console.print("[cyan]Research questions[/cyan]")
            for question in questions:
                console.print(f"  • {question}")
        resources = card.get("resources") or []
        if resources:
            console.print("[cyan]Resources[/cyan]")
            for resource in resources:
                title = resource.get("title") if isinstance(resource, dict) else str(resource)
                url = resource.get("url") if isinstance(resource, dict) else ""
                console.print(f"  • {title}" + (f" — {url}" if url else ""))
        if card.get("checkpoint"):
            console.print(f"[green]Checkpoint[/green]\n{card['checkpoint']}")


def _prompt_mastery(prompt: str) -> str:
    """Ask until we get (or can fuzzy-map to) unknown/familiar/can_explain."""
    from app.agents.policies import normalize_mastery

    allowed = {"unknown", "familiar", "can_explain"}
    while True:
        raw = typer.prompt(prompt, default="unknown")
        mastery = normalize_mastery(raw)
        if mastery in allowed:
            if mastery != raw.strip().lower().replace(" ", "_"):
                console.print(f"[dim]Interpreted as {mastery}[/dim]")
            return mastery
        console.print(
            "[yellow]Please answer unknown, familiar, or can_explain.[/yellow]"
        )


def _print_coach_reply(body: dict) -> None:
    status = body.get("answer_status")
    reply = body.get("reply") or ""
    if status == "push_back":
        console.print(f"[yellow]{reply}[/yellow]")
    elif status == "passed":
        console.print("[green]Pass.[/green]")
        if body.get("current_question"):
            console.print(f"\n[bold]Q[/bold] {body['current_question']}")
        elif reply:
            console.print(reply)
    elif status == "complete":
        console.print(f"[green]{reply}[/green]")
    else:
        console.print(reply)


def _coach_answer_loop(client: httpx.Client, user_project_id: int) -> None:
    """Prompt for answers until milestone questions are done or the learner quits."""
    console.print("[dim]Type your answer (or quit).[/dim]")
    while True:
        try:
            message = typer.prompt("Answer")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Paused. Resume with: socratic coach start[/dim]")
            return
        if message.strip().lower() in {"quit", "exit", "q"}:
            console.print("[dim]Paused. Resume with: socratic coach start[/dim]")
            return
        response = client.post(
            f"/api/v1/me/projects/{user_project_id}/coach/message",
            headers=_headers(),
            json={"message": message},
        )
        if response.status_code == 409 and "assessment" in response.text.lower():
            console.print(
                "[yellow]Finish assessment first: socratic coach start[/yellow]"
            )
            raise typer.Exit(code=1)
        if response.status_code >= 400:
            console.print(f"[red]{response.status_code}: {response.text}[/red]")
            raise typer.Exit(code=1)
        body = response.json()
        _print_coach_reply(body)
        state = body.get("learner_state") or {}
        if body.get("answer_status") == "complete" or state.get("questions_complete"):
            return


@app.command("coach")
def coach_cmd(
    action: Annotated[str, typer.Argument(help="'start' or 'message'")],
    message: Annotated[Optional[str], typer.Argument(help="Message for 'coach message'")] = None,
    user_project_id: Annotated[
        Optional[int],
        typer.Option(help="User project ID (defaults to latest enrollment)"),
    ] = None,
) -> None:
    """Start the AI coach or send a mentoring message."""
    if action not in {"start", "message"}:
        console.print("[red]Use: socratic coach start  or  socratic coach message TEXT[/red]")
        raise typer.Exit(code=1)
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        if action == "start":
            response = client.post(
                f"/api/v1/me/projects/{user_project_id}/coach/start",
                headers=_headers(),
                json={"answers": []},
            )
            if response.status_code >= 400:
                console.print(f"[red]{response.status_code}: {response.text}[/red]")
                raise typer.Exit(code=1)
            data = response.json()
            if data.get("status") == "needs_assessment":
                console.print("[bold]What do you already understand?[/bold]")
                console.print(
                    "[dim]Answers: unknown · familiar · can_explain "
                    "(typos are corrected when possible)[/dim]"
                )
                answers = []
                for question in data.get("assessment_questions") or []:
                    mastery = _prompt_mastery(question["prompt"])
                    answers.append({"concept": question["concept"], "mastery": mastery})
                response = client.post(
                    f"/api/v1/me/projects/{user_project_id}/coach/start",
                    headers=_headers(),
                    json={"answers": answers},
                )
                if response.status_code >= 400:
                    console.print(f"[red]{response.status_code}: {response.text}[/red]")
                    raise typer.Exit(code=1)
                data = response.json()
            console.print(
                f"[green]Coach {data.get('status')}[/green] session={data.get('session_id')}"
            )
            reply = data.get("reply")
            if reply:
                if data.get("learner_state", {}).get("questions_complete"):
                    console.print(f"\n[green]{reply}[/green]")
                    return
                console.print(f"\n[bold]Q[/bold] {reply}")
                _coach_answer_loop(client, user_project_id)
            return
        if not message:
            _coach_answer_loop(client, user_project_id)
            return
        response = client.post(
            f"/api/v1/me/projects/{user_project_id}/coach/message",
            headers=_headers(),
            json={"message": message},
        )
        if response.status_code == 409 and "assessment" in response.text.lower():
            console.print(
                "[yellow]Finish assessment first: socratic coach start[/yellow]"
            )
            raise typer.Exit(code=1)
        if response.status_code >= 400:
            console.print(f"[red]{response.status_code}: {response.text}[/red]")
            raise typer.Exit(code=1)
        body = response.json()
        _print_coach_reply(body)
        state = body.get("learner_state") or {}
        if not (
            body.get("answer_status") == "complete" or state.get("questions_complete")
        ):
            _coach_answer_loop(client, user_project_id)


@app.command("state")
def show_state(
    user_project_id: Annotated[
        Optional[int],
        typer.Option(help="User project ID"),
    ] = None,
) -> None:
    """Show learner state for the current milestone."""
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.get(
            f"/api/v1/me/projects/{user_project_id}/state",
            headers=_headers(),
        )
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    data = response.json()
    console.print(
        f"Q {data.get('questions_passed')}/{data.get('questions_total')} "
        f"(index={data.get('question_index')}) help={data.get('help_received')}"
    )
    if data.get("current_question"):
        console.print(f"[bold]Current[/bold] {data['current_question']}")
    if data.get("failed_at"):
        console.print(f"Failures: {len(data['failed_at'])}")
    if data.get("researched_concepts"):
        console.print("Researched: " + ", ".join(data["researched_concepts"]))


@app.command("roadmap")
def show_roadmap(
    user_project_id: Annotated[
        Optional[int],
        typer.Option(help="User project ID"),
    ] = None,
) -> None:
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.get(
            f"/api/v1/me/projects/{user_project_id}/roadmap",
            headers=_headers(),
        )
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    items = response.json()
    if not items:
        console.print("[yellow]No roadmap yet. Run: socratic coach start[/yellow]")
        return
    for item in items:
        console.print(f"\n[bold]#{item.get('order_index')} {item.get('title')}[/bold]")
        for concept in item.get("concepts") or []:
            console.print(
                f"  • {concept.get('name')} — {concept.get('teaching')} "
                f"({concept.get('mastery')})"
            )


@app.command("cards")
def show_cards(
    user_milestone_id: Annotated[
        Optional[int],
        typer.Option(help="User milestone ID (defaults to current pending)"),
    ] = None,
) -> None:
    if not isinstance(user_milestone_id, int):
        user_milestone_id = None
    with _client() as client:
        if user_milestone_id is None:
            user_project_id = _latest_user_project_id(client)
            user_milestone_id = _latest_user_milestone_id(client, user_project_id)
        response = client.get(
            f"/api/v1/me/milestones/{user_milestone_id}/cards",
            headers=_headers(),
        )
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    _print_cards(response.json())


@app.command("hint")
def ask_hint(
    user_milestone_id: Annotated[
        Optional[int],
        typer.Option(help="User milestone ID (defaults to current pending)"),
    ] = None,
) -> None:
    if not isinstance(user_milestone_id, int):
        user_milestone_id = None
    with _client() as client:
        if user_milestone_id is None:
            user_project_id = _latest_user_project_id(client)
            user_milestone_id = _latest_user_milestone_id(client, user_project_id)
        response = client.post(
            f"/api/v1/me/milestones/{user_milestone_id}/hints",
            headers=_headers(),
        )
    if response.status_code >= 400:
        console.print(f"[red]{response.status_code}: {response.text}[/red]")
        raise typer.Exit(code=1)
    body = response.json()
    if body.get("hint_blocked_reason"):
        console.print(f"[yellow]Hint held ({body['hint_blocked_reason']})[/yellow]")
    elif body.get("hint_level") is not None:
        console.print(f"[dim]hint level {body['hint_level']}[/dim]")
    console.print(body.get("reply") or "")


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
    if mode == "project":
        console.print(
            "\n[dim]Next: socratic brief → socratic sandbox init → "
            "socratic coach start → socratic coach message ...[/dim]"
        )
    else:
        console.print(
            "\n[dim]Concept mode has no AI coach yet. "
            "Use project mode for roadmap/cards/mentor, or: socratic concept show[/dim]"
        )


@sandbox_app.command("init")
def sandbox_init(
    user_project_id: Annotated[
        Optional[int],
        typer.Option("--project", help="User project ID (defaults to latest)"),
    ] = None,
) -> None:
    """Create or ensure the sandboxed workspace for a project."""
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.post(
            f"/api/v1/me/projects/{user_project_id}/sandbox",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _print_http_error(response)
        raise typer.Exit(code=1)
    data = response.json()
    console.print(
        f"[green]Sandbox ready[/green] user_project={data['user_project_id']} "
        f"path={data.get('workspace_path')}"
    )


@sandbox_app.command("ls")
def sandbox_ls(
    user_project_id: Annotated[
        Optional[int],
        typer.Option("--project", help="User project ID (defaults to latest)"),
    ] = None,
) -> None:
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.get(
            f"/api/v1/me/projects/{user_project_id}/sandbox/files",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _print_http_error(response)
        raise typer.Exit(code=1)
    table = Table("Path", "Type", "Size")
    for entry in response.json().get("files") or []:
        table.add_row(
            entry["path"],
            "dir" if entry.get("is_dir") else "file",
            "" if entry.get("size") is None else str(entry["size"]),
        )
    console.print(table)


@sandbox_app.command("read")
def sandbox_read(
    path: Annotated[str, typer.Argument(help="Relative file path in the workspace")],
    user_project_id: Annotated[
        Optional[int],
        typer.Option("--project", help="User project ID (defaults to latest)"),
    ] = None,
) -> None:
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.get(
            f"/api/v1/me/projects/{user_project_id}/sandbox/files/{path}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _print_http_error(response)
        raise typer.Exit(code=1)
    console.print(response.json().get("content", ""))


@sandbox_app.command("write")
def sandbox_write(
    path: Annotated[str, typer.Argument(help="Relative file path in the workspace")],
    content: Annotated[
        Optional[str],
        typer.Option(help="File contents (omit to read from stdin / prompt)"),
    ] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", help="Read contents from a local file"),
    ] = None,
    user_project_id: Annotated[
        Optional[int],
        typer.Option("--project", help="User project ID (defaults to latest)"),
    ] = None,
) -> None:
    if not isinstance(user_project_id, int):
        user_project_id = None
    if file is not None:
        body = file.read_text(encoding="utf-8")
    elif content is not None:
        body = content
    else:
        body = typer.prompt("Content")
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.put(
            f"/api/v1/me/projects/{user_project_id}/sandbox/files/{path}",
            headers=_headers(),
            json={"content": body},
        )
    if response.status_code >= 400:
        _print_http_error(response)
        raise typer.Exit(code=1)
    console.print(f"[green]Wrote[/green] {path}")


@sandbox_app.command("rm")
def sandbox_rm(
    path: Annotated[str, typer.Argument(help="Relative file path in the workspace")],
    user_project_id: Annotated[
        Optional[int],
        typer.Option("--project", help="User project ID (defaults to latest)"),
    ] = None,
) -> None:
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.delete(
            f"/api/v1/me/projects/{user_project_id}/sandbox/files/{path}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _print_http_error(response)
        raise typer.Exit(code=1)
    console.print(f"[green]Deleted[/green] {path}")


@sandbox_app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def sandbox_run(
    ctx: typer.Context,
    user_project_id: Annotated[
        Optional[int],
        typer.Option("--project", help="User project ID (defaults to latest)"),
    ] = None,
) -> None:
    """Run an allowlisted command in the sandbox. Example: socratic sandbox run -- python main.py"""
    argv = list(ctx.args)
    if not argv:
        console.print(
            "[red]Provide a command after -- , e.g. socratic sandbox run -- python main.py[/red]"
        )
        raise typer.Exit(code=1)
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.post(
            f"/api/v1/me/projects/{user_project_id}/sandbox/run",
            headers=_headers(),
            json={"argv": argv},
            timeout=90.0,
        )
    if response.status_code >= 400:
        _print_http_error(response)
        raise typer.Exit(code=1)
    data = response.json()
    if data.get("stdout"):
        console.print(data["stdout"], end="" if data["stdout"].endswith("\n") else "\n")
    if data.get("stderr"):
        console.print(f"[yellow]{data['stderr']}[/yellow]", end="")
    if data.get("timed_out"):
        console.print("[red]Timed out[/red]")
    console.print(f"[dim]exit={data.get('exit_code')} argv={data.get('argv')}[/dim]")
    if data.get("exit_code"):
        raise typer.Exit(code=int(data["exit_code"]))


@sandbox_app.command("test")
def sandbox_test(
    user_project_id: Annotated[
        Optional[int],
        typer.Option("--project", help="User project ID (defaults to latest)"),
    ] = None,
) -> None:
    """Run pytest in the sandbox and record the result for the coach."""
    if not isinstance(user_project_id, int):
        user_project_id = None
    with _client() as client:
        if user_project_id is None:
            user_project_id = _latest_user_project_id(client)
        response = client.post(
            f"/api/v1/me/projects/{user_project_id}/sandbox/test",
            headers=_headers(),
            timeout=90.0,
        )
    if response.status_code >= 400:
        _print_http_error(response)
        raise typer.Exit(code=1)
    data = response.json()
    outcome = data.get("outcome")
    color = "green" if outcome == "passed" else "red"
    console.print(
        f"[{color}]{outcome}[/{color}] "
        f"passed={data.get('passed')} failed={data.get('failed')} "
        f"errors={data.get('errors')} exit={data.get('exit_code')}"
    )
    if data.get("output"):
        console.print(data["output"])
    if outcome != "passed":
        console.print(
            "\n[dim]Tell the coach which layer or assumption failed "
            "(do not ask for the fix yet).[/dim]"
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

