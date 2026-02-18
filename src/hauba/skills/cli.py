"""Skill CLI — Manage Hauba skills from the command line."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hauba.core.constants import BUNDLED_SKILLS_DIR, SKILLS_DIR
from hauba.skills.loader import SkillLoader

skill_app = typer.Typer(
    name="skill",
    help="Manage Hauba skills",
    no_args_is_help=True,
)
console = Console()


@skill_app.command(name="list")
def list_skills() -> None:
    """List all installed and bundled skills."""
    loader = SkillLoader(skill_dirs=[SKILLS_DIR, BUNDLED_SKILLS_DIR])
    skills = loader.load_all()

    if not skills:
        console.print("[dim]No skills found.[/dim]")
        return

    table = Table(title="Available Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="dim")
    table.add_column("Capabilities", style="green")

    for name in sorted(skills.keys()):
        skill = skills[name]
        source = "bundled" if BUNDLED_SKILLS_DIR in skill.file_path.parents else "installed"
        caps = "; ".join(skill.capabilities[:2])
        if len(skill.capabilities) > 2:
            caps += f" (+{len(skill.capabilities) - 2} more)"
        table.add_row(name, source, caps)

    console.print(table)
    console.print(f"\n[dim]{len(skills)} skill(s) available[/dim]")


@skill_app.command()
def install(path: str = typer.Argument(..., help="Path to a .md skill file")) -> None:
    """Install a skill from a .md file."""
    source = Path(path)
    if not source.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)
    if source.suffix != ".md":
        console.print("[red]Skill files must be .md files[/red]")
        raise typer.Exit(1)

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SKILLS_DIR / source.name
    shutil.copy2(source, dest)
    console.print(f"[green]Installed skill: {source.stem} -> {dest}[/green]")


@skill_app.command()
def create(name: str = typer.Argument(..., help="Name for the new skill")) -> None:
    """Scaffold a new skill .md template."""
    slug = name.lower().replace(" ", "-")
    filename = f"{slug}.md"
    dest = Path.cwd() / filename

    if dest.exists():
        console.print(f"[red]File already exists: {dest}[/red]")
        raise typer.Exit(1)

    template = f"""# Skill: {slug}

## Capabilities
- Describe what this skill enables

## When To Use
- Describe trigger conditions for this skill

## Approach

### Phase 1: Understand
- How to analyze the problem space

### Phase 2: Plan
- How to decompose into executable steps

### Phase 3: Execute
- Step-by-step execution with decision points

### Phase 4: Verify
- How to validate the output

## Constraints
- Safety rails and anti-patterns to avoid

## Scale Considerations
- What changes at large scale

## Error Recovery
- Common failure modes and how to recover
"""
    dest.write_text(template, encoding="utf-8")
    console.print(f"[green]Created skill template: {dest}[/green]")
    console.print(f"[dim]Edit the file, then install with: hauba skill install {filename}[/dim]")


@skill_app.command()
def show(name: str = typer.Argument(..., help="Skill name to display")) -> None:
    """Display a skill's content."""
    loader = SkillLoader(skill_dirs=[SKILLS_DIR, BUNDLED_SKILLS_DIR])

    try:
        skill = loader.get(name)
    except Exception:
        console.print(f"[red]Skill not found: {name}[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        skill.raw_content,
        title=f"Skill: {skill.name}",
        border_style="cyan",
    ))
