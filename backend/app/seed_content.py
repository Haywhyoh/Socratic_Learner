"""Structured project definitions and milestone copy used by the seed command."""

from __future__ import annotations

# Milestone tuple: title, description, instructions, success_criteria
MilestoneSpec = tuple[str, str, str, str]
ProjectSpec = dict[str, object]


TASK_TRACKER: ProjectSpec = {
    "title": "Task Tracker API",
    "description": (
        "Build a production-minded FastAPI service where authenticated users create, "
        "list, and complete their own tasks."
    ),
    "objective": (
        "Design and ship a small but complete task-tracking backend with FastAPI. "
        "By the end, another engineer should be able to register/login (or use a provided "
        "token flow), create tasks, list only their own tasks, and mark tasks complete — "
        "with clear API docs and predictable errors."
    ),
    "difficulty": "beginner",
    "prerequisites": [
        "Python 3.12+",
        "HTTP and REST basics",
        "Basic SQL familiarity",
    ],
    "expected_outcome": (
        "A runnable FastAPI service with auth-aware task CRUD, ownership isolation, "
        "accurate OpenAPI docs, and a README covering migrate/seed/server/tests."
    ),
    "skills": [
        "FastAPI routing",
        "Pydantic v2 request/response schemas",
        "SQLAlchemy persistence",
        "Password hashing and JWT auth",
        "Automated API testing",
    ],
    "concepts": [
        "Ownership isolation",
        "REST status codes",
        "OpenAPI documentation",
        "Auth boundaries on mutations",
        "Milestone-sized delivery",
    ],
    "constraints": [
        "No frontend UI",
        "No real-time notifications",
        "No sharing tasks between users",
        "No file attachments",
        "Python 3.12+, FastAPI + Pydantic v2, SQLAlchemy with Postgres or SQLite",
    ],
    "tests": [
        "Happy-path create, list, and complete a task",
        "Data persists across process restart",
        "User A cannot read or complete user B's task",
        "GET /health returns 200 with a JSON status body",
    ],
    "evaluation_criteria": [
        "All three milestones completed",
        "Tests cover ownership isolation",
        "README explains how to run migrate/seed/server/tests",
        "OpenAPI docs accurately describe the endpoints",
    ],
    "extension_challenges": [
        "Add due dates and overdue filtering",
        "Allow sharing a task with another user",
        "Add soft-delete and an archive endpoint",
        "Support file attachments on tasks",
    ],
    "recommended_resources": [
        {"title": "FastAPI documentation", "url": "https://fastapi.tiangolo.com"},
        {"title": "Pydantic v2 docs", "url": "https://docs.pydantic.dev/latest/"},
        {"title": "SQLAlchemy 2.0 tutorial", "url": "https://docs.sqlalchemy.org/en/20/tutorial/"},
    ],
    "milestones": [
        (
            "Scaffold the API",
            "Stand up the FastAPI application skeleton, configuration, and a health endpoint so the service can be run and verified immediately.",
            """
What to do:
1. Create a clean project layout (app package, settings, entrypoint).
2. Add a `GET /health` endpoint that returns JSON like `{"status": "ok"}`.
3. Wire dependency management (pyproject/requirements) and a README with run steps.
4. Confirm `uvicorn` starts locally without import errors.

Hints:
- Keep settings in environment variables from day one.
- Prefer a small `main.py` that only creates the app and includes routers.
""".strip(),
            "GET /health returns HTTP 200 with a JSON status body, and the app starts cleanly via uvicorn.",
        ),
        (
            "CRUD for tasks",
            "Implement create/list/complete task endpoints backed by persistent storage, with validated request and response models.",
            """
What to do:
1. Define a Task model and Pydantic schemas (create + read).
2. Persist tasks in a database (migrations recommended).
3. Implement:
   - POST /tasks — create
   - GET /tasks — list
   - POST /tasks/{id}/complete — mark complete
4. Return sensible status codes (201 on create, 404 when missing).
5. Add at least one automated test for create + list.

Hints:
- Keep business logic out of route functions when it starts to grow.
- Make `is_completed` explicit rather than deleting completed tasks.
""".strip(),
            "A client can create a task, list tasks, and mark a task complete; data survives process restart.",
        ),
        (
            "Auth-aware ownership",
            "Protect task endpoints with authentication and enforce that each task is only visible/mutable by its owner.",
            """
What to do:
1. Add user registration/login (or issue tokens for seeded users).
2. Require auth on task endpoints.
3. Associate each created task with the authenticated user.
4. Ensure list/complete only operate on the caller’s tasks.
5. Write tests proving user A cannot complete user B’s task.

Hints:
- Prefer returning 404 for cross-user access to avoid leaking existence.
- Document the auth header format in the README.
""".strip(),
            "Authenticated ownership is enforced: users cannot read or mutate another user's tasks, verified by tests.",
        ),
    ],
}


NOTES_API: ProjectSpec = {
    "title": "Notes API with Tags",
    "description": (
        "Build a FastAPI notes backend with tagging, filtering, text search, and pagination."
    ),
    "objective": (
        "Ship a notes service that feels like a real personal knowledge API: create notes, "
        "tag them, filter by tag, search by text, and page through results."
    ),
    "difficulty": "intermediate",
    "prerequisites": [
        "Python 3.12+",
        "FastAPI basics (routing, Pydantic schemas)",
        "Relational database modeling",
    ],
    "expected_outcome": (
        "A notes API with tag filtering, text search, pagination, demo curl examples, "
        "and tests covering filter + search + pagination together."
    ),
    "skills": [
        "Query parameter design",
        "Many-to-many or array tagging strategy",
        "Case-insensitive text search",
        "Limit/offset or cursor pagination",
        "Composable list filters",
    ],
    "concepts": [
        "List endpoint complexity",
        "Normalization of tag casing",
        "Empty result sets vs errors",
        "Validation of query params (422)",
        "Response metadata for totals",
    ],
    "constraints": [
        "No full-text search engines (Postgres ILIKE / SQLite LIKE is fine)",
        "No collaborative editing",
        "No attachments",
        "FastAPI + Pydantic v2 with a relational DB",
    ],
    "tests": [
        "Create a note returns 201 with a stable id",
        "GET /notes?tag=<tag> returns only matching notes",
        "q search matches title and body case-insensitively",
        "limit and offset change the result set",
        "tag + q + pagination compose correctly",
        "Invalid query params return 422",
    ],
    "evaluation_criteria": [
        "Three milestones complete",
        "Demo curl/httpie examples in README",
        "Tests cover tag filter + search + pagination together",
        "Empty result sets return [] with 200",
    ],
    "extension_challenges": [
        "Add full-text search with Postgres tsvector",
        "Support collaborative note sharing",
        "Add file attachments on notes",
        "Implement cursor-based pagination instead of offset",
    ],
    "recommended_resources": [
        {"title": "FastAPI Query Parameters", "url": "https://fastapi.tiangolo.com/tutorial/query-params/"},
        {"title": "SQLAlchemy relationships", "url": "https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html"},
        {"title": "HTTP pagination patterns", "url": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests"},
    ],
    "milestones": [
        (
            "Note model and create endpoint",
            "Create the note persistence model and a validated create endpoint that returns the new note.",
            """
What to do:
1. Model a Note with title, body, created_at, updated_at.
2. Add POST /notes with request validation (non-empty title).
3. Return 201 with the persisted note including its id.
4. Add a basic GET /notes/{id} if useful for debugging.
""".strip(),
            "Creating a note returns HTTP 201 with a stable id and persisted fields.",
        ),
        (
            "Tags and filtering",
            "Attach tags to notes and support listing notes filtered by a single tag.",
            """
What to do:
1. Choose a tag storage approach (many-to-many recommended).
2. Allow tags on create and/or a dedicated tag update endpoint.
3. Implement GET /notes?tag=python that returns only matching notes.
4. Normalize tag casing (e.g. lowercase) and document the rule.
""".strip(),
            "GET /notes?tag=<tag> returns only notes that include that tag.",
        ),
        (
            "Search and pagination",
            "Add text search and limit/offset pagination so large note collections remain usable.",
            """
What to do:
1. Add `q` query param searching title and body (case-insensitive).
2. Add `limit` (default 20, max 100) and `offset` (default 0).
3. Combine filters: tag + q + pagination must compose.
4. Include total count in response metadata OR document why you omitted it.
""".strip(),
            "Search and pagination params change the result set correctly and compose with tag filters.",
        ),
    ],
}


LIBRARY_CATALOG: ProjectSpec = {
    "title": "Library Catalog",
    "description": (
        "Build a Django library catalog with authors, books, admin, list/detail pages, "
        "and a simple borrow workflow."
    ),
    "objective": (
        "Create a Django web app where librarians (via admin) manage authors/books, and users "
        "browse a catalog and borrow/return books with clear availability state."
    ),
    "difficulty": "beginner",
    "prerequisites": [
        "Python 3.12+",
        "Basic HTML familiarity",
        "Understanding of MVC or MTV patterns helpful",
    ],
    "expected_outcome": (
        "Admin + catalog + borrow flow works end-to-end, with README covering "
        "migrate/runserver and sample fixtures or a seed command."
    ),
    "skills": [
        "Django models and migrations",
        "Django admin registration",
        "Class- or function-based views",
        "Template inheritance",
        "Simple domain workflow (borrow)",
    ],
    "concepts": [
        "Foreign keys (Author → Book)",
        "Availability state transitions",
        "Admin as a content tool",
        "Form POST actions on detail pages",
        "Blocking invalid domain actions",
    ],
    "constraints": [
        "No payments or late fees",
        "No multi-branch inventory",
        "No complex auth roles (anonymous browse is fine if documented)",
        "Django LTS or current stable; SQLite is fine for local learning",
    ],
    "tests": [
        "Books and authors can be created in admin",
        "Catalog list and detail pages render for seeded books",
        "Borrowing flips availability and detail reflects the new state",
        "Borrowing an already-borrowed book is blocked with a clear message",
    ],
    "evaluation_criteria": [
        "Admin + catalog + borrow flow works end-to-end",
        "README includes migrate/runserver steps and sample fixtures or seed command",
        "Availability state is visible on list and detail pages",
    ],
    "extension_challenges": [
        "Add a return action to make the book available again",
        "Track who borrowed a book and when",
        "Add late fees or due dates",
        "Support multi-branch inventory",
    ],
    "recommended_resources": [
        {"title": "Django documentation", "url": "https://docs.djangoproject.com/en/stable/"},
        {"title": "Django tutorial", "url": "https://docs.djangoproject.com/en/stable/intro/tutorial01/"},
        {"title": "Django admin", "url": "https://docs.djangoproject.com/en/stable/ref/contrib/admin/"},
    ],
    "milestones": [
        (
            "Models and admin",
            "Create Author/Book models, migrations, and Django admin registration for content management.",
            """
What to do:
1. Create Author (name) and Book (title, author FK, isbn optional, is_available).
2. Makemigrations/migrate.
3. Register both models in admin with list_display and search_fields.
4. Create a superuser and add sample data.
""".strip(),
            "Books and authors can be created and edited in Django admin.",
        ),
        (
            "Catalog list views",
            "Build public list and detail pages that render books without template errors.",
            """
What to do:
1. Add URLconf routes for list and detail.
2. Create templates extending a base layout.
3. Show author name and availability on list cards/rows.
4. Detail page shows full book fields.
""".strip(),
            "Catalog list and detail pages render correctly for seeded books.",
        ),
        (
            "Borrow workflow",
            "Implement borrow (and optionally return) so availability flips and is visible on the detail page.",
            """
What to do:
1. Add a borrow action (form POST) on the detail page.
2. Only allow borrow when available; otherwise show an error.
3. Persist availability change.
4. Optional stretch: return action to make the book available again.
""".strip(),
            "Borrowing a book flips availability and the detail page reflects the new state.",
        ),
    ],
}


LEARNING_DASHBOARD: ProjectSpec = {
    "title": "Learning Dashboard",
    "description": (
        "Build a React dashboard that visualizes learner progress across courses and milestones."
    ),
    "objective": (
        "Create a React app that turns progress data into a clear learning dashboard: routes, "
        "layout, progress widgets, and filters for course/mode."
    ),
    "difficulty": "intermediate",
    "prerequisites": [
        "JavaScript fundamentals",
        "Basic React component model",
        "Familiarity with npm/Vite tooling",
    ],
    "expected_outcome": (
        "A React + Vite app with at least two routes, progress widgets from mock data, "
        "working course/mode filters, and a README explaining install/dev scripts."
    ),
    "skills": [
        "React component composition",
        "Client-side routing",
        "Mock API modules",
        "Client-side filtering",
        "Empty and loading UI states",
    ],
    "concepts": [
        "Dashboard information architecture",
        "Derived progress summaries",
        "Filter without full page reload",
        "Separating mock data from UI",
        "Shared layout with nested routes",
    ],
    "constraints": [
        "Use React + Vite (or equivalent)",
        "Mock API module first (swap for real backend later)",
        "No backend implementation required in this project",
    ],
    "tests": [
        "Two routes render inside a shared layout without console errors",
        "At least three progress widgets display from mock data",
        "Filtering updates visible widgets without a full page reload",
        "Empty/loading states render when data is missing",
    ],
    "evaluation_criteria": [
        "Filters work for course and learning mode",
        "Widgets render from mock data",
        "README explains install/dev scripts",
        "No console errors on load",
    ],
    "extension_challenges": [
        "Swap the mock module for the real Socratic Learner API",
        "Add charts for milestone completion over time",
        "Persist filter choices in URL query params",
        "Add dark mode toggle",
    ],
    "recommended_resources": [
        {"title": "React documentation", "url": "https://react.dev"},
        {"title": "Vite guide", "url": "https://vite.dev/guide/"},
        {"title": "React Router", "url": "https://reactrouter.com"},
    ],
    "milestones": [
        (
            "App shell",
            "Create the React app shell with routing and a basic shared layout.",
            """
What to do:
1. Scaffold with Vite + React.
2. Add a layout with nav links.
3. Create two routes that render placeholder pages.
4. Ensure no console errors on load.
""".strip(),
            "Two routes render inside a shared layout without console errors.",
        ),
        (
            "Progress widgets",
            "Render milestone progress cards from mock API data.",
            """
What to do:
1. Create a mock data module with at least one project and three milestones.
2. Build cards showing title + status.
3. Show a simple completion summary (e.g. 1/3 complete).
""".strip(),
            "At least three progress widgets display correctly from mock data.",
        ),
        (
            "Interactive filters",
            "Add filters for course and learning mode that update the dashboard in place.",
            """
What to do:
1. Add filter controls for course and mode.
2. Filter the mock dataset client-side.
3. Ensure changing filters does not remount the whole app / full page reload.
""".strip(),
            "Filtering updates visible widgets without a full page reload.",
        ),
    ],
}


CONTENT_CALENDAR: ProjectSpec = {
    "title": "Content Calendar Sprint",
    "description": (
        "Design a 4-week content calendar and measurement plan for a product launch."
    ),
    "objective": (
        "Produce a practical go-to-market content package: audience brief, 4-week calendar, "
        "and a measurement ritual a small team could actually run."
    ),
    "difficulty": "beginner",
    "prerequisites": [
        "Basic marketing vocabulary (audience, CTA, KPI)",
        "Ability to write clear short briefs",
    ],
    "expected_outcome": (
        "A one-page audience brief, a dated 4-week calendar with at least 12 items, "
        "and a KPI plan distinguishing leading vs lagging indicators with owners."
    ),
    "skills": [
        "Audience and positioning writing",
        "Multi-channel content planning",
        "CTA design",
        "KPI selection and ownership",
        "Weekly review ritual design",
    ],
    "concepts": [
        "Audience / pain / promise / proof",
        "Leading vs lagging indicators",
        "Channel mix across a launch window",
        "Measurement cadence",
        "Executable briefs vs generic personas",
    ],
    "constraints": [
        "Deliverables are documents/plans (no ad spend required)",
        "Brief must fit one page",
        "Calendar must be specific and dated, not vague themes only",
    ],
    "tests": [
        "Brief names audience, pain, promise, and proof",
        "Calendar includes at least 12 dated content items with channels and CTAs",
        "Plan lists leading and lagging indicators with owners",
        "Weekly review agenda is concrete enough to run",
    ],
    "evaluation_criteria": [
        "Brief is specific (not generic persona fluff)",
        "Calendar has >= 12 dated items",
        "Measurement plan distinguishes leading vs lagging indicators",
        "Each metric has a named owner",
    ],
    "extension_challenges": [
        "Add a paid acquisition layer with budget caps",
        "Build a Notion/Sheets template others can fork",
        "Define a post-launch week 5–6 sustain plan",
        "Map each calendar item to a funnel stage",
    ],
    "recommended_resources": [
        {"title": "Jobs to Be Done overview", "url": "https://jtbd.info"},
        {"title": "Google Analytics KPIs intro", "url": "https://support.google.com/analytics/answer/11583528"},
        {"title": "Content marketing strategy guide", "url": "https://contentmarketinginstitute.com/articles/content-marketing-strategy-guide/"},
    ],
    "milestones": [
        (
            "Audience brief",
            "Write a one-page audience and positioning brief that a creator could execute from.",
            """
What to include:
- Target audience
- Pain
- Promise
- Proof / differentiation
Keep it to one page.
""".strip(),
            "Brief names audience, pain, promise, and proof.",
        ),
        (
            "Four-week calendar",
            "Produce a 4-week calendar with channels, dates, and CTAs.",
            """
What to include:
- At least 12 dated content items
- Channel per item (email, social, blog, etc.)
- Primary CTA per item
""".strip(),
            "Calendar includes at least 12 dated content items with channels and CTAs.",
        ),
        (
            "Measurement plan",
            "Define KPIs and a weekly review ritual with clear owners.",
            """
What to include:
- Leading indicators
- Lagging indicators
- Weekly review agenda
- Owner for each metric
""".strip(),
            "Plan lists leading and lagging indicators with owners.",
        ),
    ],
}


ALL_PROJECTS: list[ProjectSpec] = [
    TASK_TRACKER,
    NOTES_API,
    LIBRARY_CATALOG,
    LEARNING_DASHBOARD,
    CONTENT_CALENDAR,
]
