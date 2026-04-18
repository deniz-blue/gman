from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import shlex
import subprocess
import time

from .executor import GitCommandExecutor
from .models import AppConfig, FetchResult, Repository, RunResult
from .output import create_output_printer
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
    parser.add_argument("-c", "--config", type=Path, default=None, help="Path to the config file")
    parser.add_argument(
        "-o",
        "--output",
        choices=("pretty", "json", "whitespace"),
        default="pretty",
        help="Output format",
    )
    parser.add_argument(
        "-P",
        "--show-path",
        action="store_true",
        help="Include path column in pretty output",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List discovered repositories with optional status")
    _add_repo_selection_args(list_parser, sort_choices=("path", "name", "branch", "ahead", "behind"))
    list_parser.add_argument("-S", "--status", action="store_true", help="Include status details")
    list_parser.add_argument("-D", "--dirty", action="store_true", help="Only show repos with local changes")
    list_parser.add_argument(
        "-u",
        "--clean",
        action="store_true",
        help="Only show repos with no ahead/behind counts and no local changes",
    )

    fetch_parser = subparsers.add_parser("fetch", help="Fetch all repositories")
    _add_repo_selection_args(fetch_parser, sort_choices=("path", "name"))

    run_parser = subparsers.add_parser("run", help="Run a shell command in filtered repositories")
    _add_repo_selection_args(run_parser, sort_choices=("path", "name"))
    run_parser.add_argument("run_command", help="Shell command to run in each repository")
    run_parser.add_argument(
        "-x",
        "--fail-fast",
        action="store_true",
        help="Stop after the first repository command failure",
    )
    run_parser.add_argument(
        "-i",
        "--pipe",
        dest="pipe_stdout",
        action="store_true",
        help="Print each repository command stdout to terminal",
    )

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
    parser.add_argument(
        "-n",
        "--name",
        dest="name_contains",
        default=None,
        help="Case-insensitive repository name substring filter",
    )
    parser.add_argument(
        "-p",
        "--path",
        dest="path_contains",
        default=None,
        help="Case-insensitive repository path substring filter",
    )
    parser.add_argument(
        "-r",
        "--root",
        dest="under_root",
        type=Path,
        action="append",
        default=None,
        help="Only include repositories under this root (can be repeated)",
    )
    parser.add_argument("-s", "--sort", dest="sort_by", choices=sort_choices, default="path", help="Sort key")
    parser.add_argument("-d", "--desc", dest="descending", action="store_true", help="Sort descending")
    parser.add_argument("-l", "--limit", type=int, default=None, help="Maximum number of rows to output")


def _run_command_in_repositories(
    repositories: list[Repository],
    command: str,
    *,
    fail_fast: bool = False,
    pipe_stdout: bool = False,
) -> list[RunResult]:
    results: list[RunResult] = []
    for repository in repositories:
        started_at = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=repository.path,
            text=True,
            capture_output=True,
            check=False,
            shell=True,
        )
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        if pipe_stdout and completed.stdout:
            print(completed.stdout, end="")
        results.append(
            RunResult(
                repository=repository,
                command=command,
                success=completed.returncode == 0,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )
        if fail_fast and completed.returncode != 0:
            break
    return results


def _fetch_results_from_run_results(run_results: list[RunResult]) -> list[FetchResult]:
    fetch_results: list[FetchResult] = []
    for result in run_results:
        output = "\n".join(value for value in (result.stdout.strip(), result.stderr.strip()) if value)
        updated_refs = tuple(line.strip() for line in output.splitlines() if line.strip())
        fetch_results.append(
            FetchResult(
                repository=result.repository,
                success=result.success,
                error_message=result.stderr.strip() if not result.success else None,
                duration_ms=result.duration_ms,
                updated_refs=updated_refs,
            )
        )
    return fetch_results


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.load(args.config)
    printer = create_output_printer(args.output, show_path=args.show_path)
    if args.command == "clone":
        destination = config.clone_destination(args.remote)
        GitCommandExecutor.clone(args.remote, destination)
        printer.print_clone_result(args.remote, destination)

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
            printer.print_repositories(repositories)
            return 0

        rows = status_rows(repositories)
        row_operators = options.status_filters() + [
            StatusSort(sort_by=selection.sort_by, descending=selection.descending),
            LimitFilter(selection.limit),
        ]
        rows = apply_operators(rows, row_operators)

        if options.should_print_status(selection.sort_by):
            printer.print_status_rows(rows)
        else:
            printer.print_repositories([row.repository for row in rows])
        return 0

    if args.command == "fetch":
        repositories = apply_operators(repositories, selection.repository_ordering() + selection.repository_limit())
        fetch_command = f"git fetch --prune {shlex.quote(config.default_remote_name)}"
        run_results = _run_command_in_repositories(repositories, fetch_command)
        printer.print_fetch_results(_fetch_results_from_run_results(run_results))
        return 0 if all(result.success for result in run_results) else 1

    if args.command == "run":
        repositories = apply_operators(repositories, selection.repository_ordering() + selection.repository_limit())
        run_results = _run_command_in_repositories(
            repositories,
            args.run_command,
            fail_fast=args.fail_fast,
            pipe_stdout=args.pipe_stdout,
        )
        printer.print_run_results(run_results)
        return 0 if all(result.success for result in run_results) else 1

    return 1