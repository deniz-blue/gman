from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import json
import re
import sys

from .models import FetchResult, Repository, RunResult
from .selectors import StatusRow


class OutputPrinter(ABC):
    @abstractmethod
    def print_repositories(self, repositories: list[Repository]) -> None:
        raise NotImplementedError

    @abstractmethod
    def print_status_rows(self, rows: list[StatusRow]) -> None:
        raise NotImplementedError

    @abstractmethod
    def print_fetch_results(self, results: list[FetchResult]) -> None:
        raise NotImplementedError

    @abstractmethod
    def print_run_results(self, results: list[RunResult]) -> None:
        raise NotImplementedError

    @abstractmethod
    def print_clone_result(self, remote: str, destination: Path) -> None:
        raise NotImplementedError


class PrettyPrinter(OutputPrinter):
    _ansi_re = re.compile(r"\x1b\[[0-9;]*m")

    def __init__(self, use_color: bool | None = None, show_path: bool = False, max_path_length: int = 52) -> None:
        self.use_color = sys.stdout.isatty() if use_color is None else use_color
        self.show_path = show_path
        self.max_path_length = max_path_length

    def print_repositories(self, repositories: list[Repository]) -> None:
        headers = ["NAME"]
        if self.show_path:
            headers.append("PATH")

        rows: list[list[str]] = []
        for repository in repositories:
            row = [self._bold(repository.name)]
            if self.show_path:
                row.append(self._blue(self._shorten_path(str(repository.path))))
            rows.append(row)
        self._print_table(headers, rows)

    def print_status_rows(self, rows: list[StatusRow]) -> None:
        headers = ["NAME", "BRANCH", "TRACKING", "DELTA", "STATE"]
        if self.show_path:
            headers.append("PATH")

        table_rows: list[list[str]] = []
        for row in rows:
            status = row.status
            tracking_branch = status.tracking_branch or "-"
            clean_or_dirty = self._green("clean") if not status.is_dirty else self._yellow("dirty")
            table_row = [
                self._bold(row.repository.name),
                status.current_branch,
                tracking_branch,
                self._delta_cell(status.ahead_count, status.behind_count),
                clean_or_dirty,
            ]
            if self.show_path:
                table_row.append(self._blue(self._shorten_path(str(row.repository.path))))
            table_rows.append(table_row)
        self._print_table(headers, table_rows)

    def print_fetch_results(self, results: list[FetchResult]) -> None:
        headers = ["NAME", "RESULT", "DURATION_MS"]
        if self.show_path:
            headers.append("PATH")

        rows: list[list[str]] = []
        for result in results:
            outcome = self._green("ok") if result.success else self._red("failed")
            row = [self._bold(result.repository.name), outcome, str(result.duration_ms)]
            if self.show_path:
                row.append(self._blue(self._shorten_path(str(result.repository.path))))
            rows.append(row)
        self._print_table(headers, rows)

    def print_run_results(self, results: list[RunResult]) -> None:
        headers = ["NAME", "RESULT", "EXIT", "DURATION_MS"]
        if self.show_path:
            headers.append("PATH")

        rows: list[list[str]] = []
        for result in results:
            outcome = self._green("ok") if result.success else self._red("failed")
            row = [
                self._bold(result.repository.name),
                outcome,
                str(result.exit_code),
                str(result.duration_ms),
            ]
            if self.show_path:
                row.append(self._blue(self._shorten_path(str(result.repository.path))))
            rows.append(row)
        self._print_table(headers, rows)

    def print_clone_result(self, remote: str, destination: Path) -> None:
        headers = ["NAME", "REMOTE", "RESULT"]
        row = [self._bold(destination.name), remote, self._green("cloned")]
        if self.show_path:
            headers.append("PATH")
            row.append(self._blue(self._shorten_path(str(destination))))
        self._print_table(headers, [row])

    def _shorten_path(self, path_text: str) -> str:
        if self.max_path_length <= 0 or len(path_text) <= self.max_path_length:
            return path_text

        # Keep both ends so users can identify root and repository name quickly.
        head_len = (self.max_path_length - 3) // 2
        tail_len = self.max_path_length - 3 - head_len
        return f"{path_text[:head_len]}...{path_text[-tail_len:]}"

    def _style(self, text: str, code: str) -> str:
        if not self.use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def _print_table(self, headers: list[str], rows: list[list[str]]) -> None:
        if not headers:
            return

        widths = [self._visible_length(header) for header in headers]
        for row in rows:
            for index, cell in enumerate(row):
                widths[index] = max(widths[index], self._visible_length(cell))

        header_cells = [self._header_cell(headers[index], widths[index]) for index in range(len(headers))]
        print("  ".join(header_cells))
        for row in rows:
            print("  ".join(self._pad_cell(row[index], widths[index]) for index in range(len(headers))))

    def _header_cell(self, text: str, width: int) -> str:
        styled = self._header_style(text)
        return styled + (" " * (width - self._visible_length(styled)))

    def _header_style(self, text: str) -> str:
        return self._style(text, "1;4;36")

    def _visible_length(self, text: str) -> int:
        return len(self._ansi_re.sub("", text))

    def _pad_cell(self, text: str, width: int) -> str:
        return text + (" " * (width - self._visible_length(text)))

    def _delta_cell(self, ahead_count: int, behind_count: int) -> str:
        parts: list[str] = []
        if ahead_count > 0:
            parts.append(self._green(f"+{ahead_count}"))
        if behind_count > 0:
            parts.append(self._red(f"-{behind_count}"))
        if not parts:
            return "0"
        return " ".join(parts)

    def _green(self, text: str) -> str:
        return self._style(text, "32")

    def _red(self, text: str) -> str:
        return self._style(text, "31")

    def _yellow(self, text: str) -> str:
        return self._style(text, "33")

    def _blue(self, text: str) -> str:
        return self._style(text, "34")

    def _bold(self, text: str) -> str:
        return self._style(text, "1")


class JsonPrinter(OutputPrinter):
    def print_repositories(self, repositories: list[Repository]) -> None:
        payload = [{"path": str(repository.path), "name": repository.name} for repository in repositories]
        print(json.dumps(payload, indent=2, sort_keys=True))

    def print_status_rows(self, rows: list[StatusRow]) -> None:
        payload = [
            {
                "path": str(row.repository.path),
                "name": row.repository.name,
                "current_branch": row.status.current_branch,
                "head_sha": row.status.head_sha,
                "tracking_branch": row.status.tracking_branch,
                "ahead_count": row.status.ahead_count,
                "behind_count": row.status.behind_count,
                "is_dirty": row.status.is_dirty,
                "is_detached_head": row.status.is_detached_head,
                "last_commit_date": row.status.last_commit_date.isoformat(),
            }
            for row in rows
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))

    def print_fetch_results(self, results: list[FetchResult]) -> None:
        payload = [
            {
                "path": str(result.repository.path),
                "name": result.repository.name,
                "success": result.success,
                "error_message": result.error_message,
                "duration_ms": result.duration_ms,
                "updated_refs": list(result.updated_refs),
            }
            for result in results
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))

    def print_run_results(self, results: list[RunResult]) -> None:
        payload = [
            {
                "path": str(result.repository.path),
                "name": result.repository.name,
                "command": result.command,
                "success": result.success,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            for result in results
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))

    def print_clone_result(self, remote: str, destination: Path) -> None:
        payload = {
            "remote": remote,
            "destination": str(destination),
            "success": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))


class WhitespacePrinter(OutputPrinter):
    def print_repositories(self, repositories: list[Repository]) -> None:
        for repository in repositories:
            print(f"{repository.path}\t{repository.name}")

    def print_status_rows(self, rows: list[StatusRow]) -> None:
        for row in rows:
            status = row.status
            tracking_branch = status.tracking_branch or "-"
            print(
                f"{row.repository.path}\t{row.repository.name}\t{status.current_branch}\t"
                f"{status.head_sha}\t{tracking_branch}\t{status.ahead_count}\t{status.behind_count}\t"
                f"{str(status.is_dirty).lower()}\t{str(status.is_detached_head).lower()}\t"
                f"{status.last_commit_date.isoformat()}"
            )

    def print_fetch_results(self, results: list[FetchResult]) -> None:
        for result in results:
            outcome = "ok" if result.success else "failed"
            error = result.error_message or ""
            print(f"{result.repository.path}\t{result.repository.name}\t{outcome}\t{result.duration_ms}\t{error}")

    def print_run_results(self, results: list[RunResult]) -> None:
        for result in results:
            outcome = "ok" if result.success else "failed"
            stderr_line = result.stderr.splitlines()[0] if result.stderr else ""
            print(
                f"{result.repository.path}\t{result.repository.name}\t{outcome}\t"
                f"{result.exit_code}\t{result.duration_ms}\t{stderr_line}"
            )

    def print_clone_result(self, remote: str, destination: Path) -> None:
        print(f"{remote}\t{destination}")


def create_output_printer(output_format: str, show_path: bool = False) -> OutputPrinter:
    if output_format == "json":
        return JsonPrinter()
    if output_format == "whitespace":
        return WhitespacePrinter()
    return PrettyPrinter(show_path=show_path)
