from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import subprocess

from .executor import GitCommandExecutor
from .models import AppConfig, Repository, RepositoryStatus
from .selectors import (
    ListOptions,
    RepositorySelection,
    LimitFilter,
    StatusSort,
    apply_operators,
    status_rows,
)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="gman", description="Manage locally cloned Git repositories")
    parser.add_argument("--config", type=Path, default=None, help="Path to the config file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List discovered repositories with optional status")
    _add_repo_selection_args(list_parser, sort_choices=("path", "name", "branch", "ahead", "behind"))
    list_parser.add_argument("--status", action="store_true", help="Include status details")
    list_parser.add_argument("--dirty-only", action="store_true", help="Only show repos with local changes")
    list_parser.add_argument(
        "--up-to-date-only",
        action="store_true",
        help="Only show repos with no ahead/behind counts and no local changes",
    )

    fetch_parser = subparsers.add_parser("fetch", help="Fetch all repositories")
    _add_repo_selection_args(fetch_parser, sort_choices=("path", "name"))

    clone_parser = subparsers.add_parser("clone", help="Clone a repository into configured destination format")
    clone_parser.add_argument("remote", help="Remote URL (https, ssh, or local path)")
    clone_parser.add_argument(
        "post_clone_command",
        nargs="?",
        default=None,
        help="Optional shell command to execute inside the cloned directory",
    )

    return parser


def _add_repo_selection_args(parser: ArgumentParser, sort_choices: tuple[str, ...]) -> None:
    parser.add_argument("--name-contains", default=None, help="Case-insensitive repository name substring filter")
    parser.add_argument("--path-contains", default=None, help="Case-insensitive repository path substring filter")
    parser.add_argument(
        "--under-root",
        type=Path,
        action="append",
        default=None,
        help="Only include repositories under this root (can be repeated)",
    )
    parser.add_argument("--sort-by", choices=sort_choices, default="path", help="Sort key")
    parser.add_argument("--descending", action="store_true", help="Sort descending")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of rows to output")


def _print_repository_status(repository: Repository, status: RepositoryStatus) -> None:
    tracking_branch = status.tracking_branch or "-"
    print(
        f"{repository.path} | branch={status.current_branch} | head={status.head_sha[:12]} | "
        f"tracking={tracking_branch} | ahead={status.ahead_count} | behind={status.behind_count} | "
        f"dirty={status.is_dirty} | detached={status.is_detached_head}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.load(args.config)
    if args.command == "clone":
        destination = config.clone_destination(args.remote)
        GitCommandExecutor.clone(args.remote, destination)
        print(f"cloned {args.remote} -> {destination}")

        if args.post_clone_command:
            completed = subprocess.run(
                args.post_clone_command,
                cwd=destination,
                text=True,
                check=False,
                shell=True,
            )
            return completed.returncode
        return 0

    selection = RepositorySelection.from_args(args)
    repositories = apply_operators(config.repositories(), selection.repository_filters())

    if args.command == "list":
        options = ListOptions.from_args(args)
        if not options.requires_status(selection.sort_by):
            repositories = apply_operators(repositories, selection.repository_ordering() + selection.repository_limit())
            for repository in repositories:
                print(f"{repository.path} | {repository.name}")
            return 0

        rows = status_rows(repositories)
        row_operators = options.status_filters() + [
            StatusSort(sort_by=selection.sort_by, descending=selection.descending),
            LimitFilter(selection.limit),
        ]
        rows = apply_operators(rows, row_operators)

        for row in rows:
            if options.should_print_status(selection.sort_by):
                _print_repository_status(row.repository, row.status)
            else:
                print(f"{row.repository.path} | {row.repository.name}")
        return 0

    if args.command == "fetch":
        repositories = apply_operators(repositories, selection.repository_ordering() + selection.repository_limit())
        for repository in repositories:
            result = repository.fetch(config.default_remote_name)
            outcome = "ok" if result.success else "failed"
            print(f"{repository.path} | {outcome} | {result.duration_ms}ms")
        return 0

    return 1