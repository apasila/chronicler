from __future__ import annotations
import os
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chronicler.config.settings import load_config
from chronicler.core.daemon import start_daemon, stop_daemon, get_daemon_status
from chronicler.storage.db import Database
from chronicler.storage.map import MapManager
from chronicler.storage.schema import Project

app = typer.Typer(
    name="chronicler",
    help="Chronicler — automatic code change logging for AI agents",
    no_args_is_help=True,
)
console = Console()


def _get_db() -> Database:
    db_path = Path.home() / ".config" / "chronicler" / "chronicler.db"
    db = Database(str(db_path))
    db.initialize()
    return db


def _detect_framework(path: Path) -> str | None:
    checks = [
        (["next.config.js", "next.config.ts"], "nextjs"),
        (["vite.config.ts", "vite.config.js"], "vite"),
        (["manage.py"], "django"),
        (["pyproject.toml"], "python"),
    ]
    for files, name in checks:
        if any((path / f).exists() for f in files):
            return name
    return None


def _get_git_branch(project_path: str) -> str | None:
    import subprocess
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, cwd=project_path)
        return r.stdout.strip() or None
    except Exception:
        return None


@app.command()
def init(
    name: str = typer.Option(None, help="Project name"),
    path: str = typer.Option(".", help="Project path"),
):
    """Set up a project for watching."""
    project_path = Path(path).resolve()
    console.print(Panel("[bold]Chronicler — Project Setup[/bold]", expand=False))

    project_name = name or typer.prompt("Project name", default=project_path.name)
    git_enabled = (project_path / ".git").exists()
    if git_enabled:
        console.print("Git repository detected ✓")

    framework = _detect_framework(project_path)
    if framework:
        console.print(f"Framework detected: {framework} ✓")

    console.print("\nLog mode:\n  1. debounced (recommended)\n  2. every_save\n  3. session_only")
    log_mode = {"1": "debounced", "2": "every_save", "3": "session_only"}.get(
        typer.prompt("Choice", default="1"), "debounced"
    )

    console.print("\nModel tier:\n  1. cloud via Groq\n  2. local via Ollama")
    tier = "cloud" if typer.prompt("Choice", default="1") == "1" else "local"

    if tier == "cloud" and os.environ.get("GROQ_API_KEY"):
        console.print("GROQ_API_KEY found in environment ✓")
    elif tier == "cloud":
        console.print("[yellow]Warning: GROQ_API_KEY not set[/yellow]")

    chronicler_dir = project_path / ".chronicler"
    chronicler_dir.mkdir(exist_ok=True)
    (chronicler_dir / "handoffs").mkdir(exist_ok=True)

    (chronicler_dir / "config.toml").write_text(
        f'[project]\nname = "{project_name}"\nframework = "{framework or ""}"\nlanguages = []\n\n'
        f'[logging]\nmode = "{log_mode}"\n\n[models]\ntier = "{tier}"\n'
    )

    db = _get_db()
    if db.get_project_by_path(str(project_path)) is None:
        db.insert_project(Project(
            id=str(uuid.uuid4()), name=project_name, path=str(project_path),
            created_at=datetime.utcnow(), git_enabled=git_enabled,
            primary_language="unknown", languages=[], framework=framework,
            description=None, log_mode=log_mode, ignore_patterns=[], tags=[],
        ))

    MapManager(str(chronicler_dir)).create_initial(project_name, framework, [])

    gitignore = project_path / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".chronicler/" not in content:
            gitignore.write_text(content + "\n.chronicler/\n")

    console.print("\n" + "─" * 40)
    console.print("✓ .chronicler/config.toml created")
    console.print("✓ Project registered in chronicler.db")
    console.print("✓ Run [bold]chronicler start[/bold] to begin watching")


@app.command()
def start(
    path: str = typer.Option(".", help="Project path"),
    foreground: bool = typer.Option(False, "--foreground", "-f"),
):
    """Start the daemon."""
    project_path = Path(path).resolve()
    if not (project_path / ".chronicler").exists():
        console.print("[red]Not initialized. Run: chronicler init[/red]")
        raise typer.Exit(1)

    config = load_config(str(project_path))
    db = _get_db()
    project = db.get_project_by_path(str(project_path))
    if project is None:
        console.print("[red]Not registered. Run: chronicler init[/red]")
        raise typer.Exit(1)

    if foreground:
        _run_watcher(project, config, db)
    else:
        _daemonize(project_path, project, config, db)


@app.command()
def stop(path: str = typer.Option(".", help="Project path")):
    """Stop the daemon."""
    project_path = Path(path).resolve()
    status = get_daemon_status(project_path)
    if status == "stopped":
        console.print("No daemon running.")
        return
    pid_file = project_path / ".chronicler" / "chronicler.pid"
    pid = int(pid_file.read_text().strip())
    stop_daemon(project_path)
    console.print(f"Stopped daemon (PID {pid})")


@app.command()
def status(path: str = typer.Option(".", help="Project path")):
    """Show what's being watched and recent activity."""
    project_path = Path(path).resolve()
    if not (project_path / ".chronicler").exists():
        console.print("[yellow]Not initialized. Run: chronicler init[/yellow]")
        return

    db = _get_db()
    project = db.get_project_by_path(str(project_path))
    if project is None:
        console.print("[yellow]Not registered. Run: chronicler init[/yellow]")
        return

    running = (project_path / ".chronicler" / "chronicler.pid").exists()
    console.print(Panel(f"[bold]{project.name}[/bold]", expand=False))
    console.print(f"Daemon: {'[green]running[/green]' if running else '[red]stopped[/red]'}")
    console.print(f"Mode: {project.log_mode}")

    entries = db.get_recent_entries(project.id, limit=5)
    if entries:
        t = Table(title="Recent Activity")
        t.add_column("Time"); t.add_column("File"); t.add_column("Type"); t.add_column("Summary")
        for e in entries:
            t.add_row(e.timestamp.strftime("%H:%M:%S"), e.file.relative_path,
                      e.change.type, e.change.summary[:60])
        console.print(t)
    else:
        console.print("No entries yet.")


@app.command("log")
def view_log(
    path: str = typer.Option(".", help="Project path"),
    limit: int = typer.Option(20),
    change_type: str = typer.Option(None),
):
    """View recent log entries."""
    db = _get_db()
    project = db.get_project_by_path(str(Path(path).resolve()))
    if project is None:
        console.print("[yellow]Not initialized.[/yellow]"); return

    entries = db.get_recent_entries(project.id, limit=limit)
    if change_type:
        entries = [e for e in entries if e.change.type == change_type]
    if not entries:
        console.print("No entries found."); return

    t = Table(title=f"Log — {project.name}")
    t.add_column("Timestamp", style="dim"); t.add_column("File")
    t.add_column("Type", style="bold"); t.add_column("Impact"); t.add_column("Summary")
    colors = {"low": "green", "medium": "yellow", "high": "red"}
    for e in entries:
        c = colors.get(e.change.impact, "white")
        t.add_row(e.timestamp.strftime("%Y-%m-%d %H:%M"), e.file.relative_path,
                  e.change.type, f"[{c}]{e.change.impact}[/{c}]", e.change.summary[:70])
    console.print(t)


@app.command()
def handoff(
    path: str = typer.Option(".", help="Project path"),
    sessions: int = typer.Option(5),
):
    """Generate a handoff packet for an AI agent."""
    project_path = Path(path).resolve()
    db = _get_db()
    project = db.get_project_by_path(str(project_path))
    if project is None:
        console.print("[yellow]Not initialized.[/yellow]"); return

    config = load_config(str(project_path))
    from chronicler.llm.classifier import HandoffGenerator
    map_mgr = MapManager(str(project_path / ".chronicler"))
    output = HandoffGenerator(config).generate(project, map_mgr.read(), db, sessions)

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    out_path = project_path / ".chronicler" / "handoffs" / f"{date_str}-handoff.md"
    out_path.write_text(output)
    console.print(output)
    console.print(f"\n[dim]Saved to {out_path}[/dim]")


@app.command("map")
def view_map(path: str = typer.Option(".", help="Project path")):
    """View the master map."""
    content = MapManager(str(Path(path).resolve() / ".chronicler")).read()
    if not content:
        console.print("[yellow]No map found. Run: chronicler init[/yellow]")
    else:
        console.print(content)


@app.command()
def ui(
    port: int = typer.Option(8765, help="Port to serve the UI on"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser automatically"),
):
    """Launch the Chronicler web dashboard."""
    import socket
    # Check if port is available
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            console.print(f"[red]Port {port} is already in use.[/red]")
            console.print(f"Try: [bold]chronicler ui --port {port + 1}[/bold]")
            raise typer.Exit(1)

    import uvicorn
    from chronicler.ui.server import create_app

    url = f"http://localhost:{port}"
    console.print(f"[bold]Chronicler UI[/bold] → {url}")
    console.print("Press [bold]Ctrl+C[/bold] to stop.\n")

    if not no_open:
        webbrowser.open(url)

    app_instance = create_app()
    uvicorn.run(app_instance, host="127.0.0.1", port=port, log_level="warning")


def _run_watcher(project, config, db) -> None:
    from chronicler.core.watcher import Watcher
    from chronicler.core.differ import Differ
    from chronicler.core.context import ContextAssembler
    from chronicler.llm.classifier import EntryClassifier, MapUpdater
    from chronicler.storage.schema import LogEntry, FileInfo, MAP_TRIGGER_PATTERNS
    import fnmatch as _fnmatch

    differ = Differ(project_path=project.path, git_enabled=project.git_enabled)
    context_asm = ContextAssembler(db=db)
    classifier = EntryClassifier(config=config)
    map_updater = MapUpdater(config=config)
    map_mgr = MapManager(str(Path(project.path) / ".chronicler"))

    def on_change(file_path: str) -> None:
        try:
            diff = differ.diff_file(file_path)
            if diff is None or (diff.lines_added == 0 and diff.lines_removed == 0):
                return
            session = context_asm.get_or_create_session(
                project.id, config.logging.session_gap_minutes
            )
            recent_ctx = context_asm.get_recent_context(diff.relative_path, project.id)
            change_info, llm_info = classifier.classify(
                diff, project.name, project.framework, recent_ctx
            )
            entry = LogEntry(
                id=str(uuid.uuid4()), project_id=project.id, session_id=session.id,
                timestamp=datetime.utcnow(),
                file=FileInfo(path=file_path, relative_path=diff.relative_path,
                              extension=Path(file_path).suffix, language=diff.language,
                              is_new=diff.is_new_file, is_deleted=diff.is_deleted,
                              is_renamed=False, renamed_from=None),
                change=change_info, llm=llm_info,
                context={"git_branch": _get_git_branch(project.path)},
                tags=[], manually_edited=False, notes=None,
            )
            db.insert_log_entry(entry)
            console.print(
                f"[dim]{entry.timestamp.strftime('%H:%M:%S')}[/dim] "
                f"{diff.relative_path} → {change_info.type}: {change_info.summary[:60]}"
            )
            # Trigger map update if file matches MAP_TRIGGER_PATTERNS
            fname = Path(file_path).name
            if any(_fnmatch.fnmatch(fname, p) or _fnmatch.fnmatch(diff.relative_path, p)
                   for p in MAP_TRIGGER_PATTERNS):
                updates = map_updater.update(map_mgr.read(), [entry])
                if any(v for v in updates.values() if v):
                    map_mgr.update(updates)
        except Exception as e:
            console.print(f"[red]Error processing {file_path}: {e}[/red]")

    ignore = config.ignore.patterns + [".chronicler/**"]
    watcher = Watcher(project_path=project.path, ignore_patterns=ignore,
                      on_change=on_change, debounce_seconds=config.logging.debounce_seconds)
    console.print(f"Watching [bold]{project.path}[/bold]... (Ctrl+C to stop)\n")
    watcher.start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        console.print("\nStopped.")


def _daemonize(project_path: Path, project, config, db) -> None:
    start_daemon(project_path)
    console.print(f"Daemon started. Run [bold]chronicler stop[/bold] to stop.")


if __name__ == "__main__":
    app()
