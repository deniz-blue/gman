from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
import json
import os
import re
from urllib.parse import urlparse


@dataclass(slots=True, frozen=True)
class FetchResult:
    repository: Repository
    success: bool
    error_message: str | None = None
    duration_ms: int = 0
    updated_refs: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class RunResult:
    repository: Repository
    command: str
    success: bool
    exit_code: int
    duration_ms: int
    stdout: str = ""
    stderr: str = ""


@dataclass(slots=True)
class AppConfig:
    watched_roots: list[Path] = field(default_factory=list)
    ignore_patterns: list[str] = field(default_factory=list)
    default_remote_name: str = "origin"
    clone_into: str = "~/Source/Repos/{owner}/{name}"

    @classmethod
    def load(cls, config_path: Path | None = None) -> AppConfig:
        path = config_path or cls.default_config_path()
        if not path.exists():
            return cls(watched_roots=[Path.cwd().resolve()])

        data = json.loads(path.read_text(encoding="utf-8"))
        watched_roots = [Path(value).expanduser().resolve() for value in data.get("watched_roots", [])]
        if not watched_roots:
            watched_roots = [Path.cwd().resolve()]
        return cls(
            watched_roots=watched_roots,
            ignore_patterns=list(data.get("ignore_patterns", [])),
            default_remote_name=str(data.get("default_remote_name", "origin")),
            clone_into=str(data.get("cloneInto", data.get("clone_into", "~/Source/Repos/{owner}/{name}"))),
        )

    @staticmethod
    def default_config_path() -> Path:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return config_home / "gman" / "config.json"

    def save(self, config_path: Path | None = None) -> None:
        path = config_path or self.default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "watched_roots": [str(root) for root in self.watched_roots],
            "ignore_patterns": self.ignore_patterns,
            "default_remote_name": self.default_remote_name,
            "cloneInto": self.clone_into,
        }
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def clone_destination(self, remote: str) -> Path:
        tokens = self._clone_tokens(remote)
        rendered = self.clone_into.format(**tokens)
        return Path(rendered).expanduser().resolve()

    @staticmethod
    def _clone_tokens(remote: str) -> dict[str, str]:
        remote = remote.strip()
        scp_match = re.match(r"^(?:(?P<user>[^@]+)@)?(?P<host>[^:]+):(?P<path>.+)$", remote)
        if scp_match and "/" in scp_match.group("path"):
            host = scp_match.group("host")
            remote_path = scp_match.group("path")
            return AppConfig._tokens_from_path(host=host, remote_path=remote_path)

        parsed = urlparse(remote)
        if parsed.scheme and parsed.path:
            host = parsed.hostname or "local"
            remote_path = parsed.path.lstrip("/")
            return AppConfig._tokens_from_path(host=host, remote_path=remote_path)

        local_path = Path(remote)
        name = local_path.name
        if name.endswith(".git"):
            name = name[:-4]
        return {
            "host": "local",
            "owner": "local",
            "name": name or "repository",
            "path": str(local_path),
            "remote": remote,
        }

    @staticmethod
    def _tokens_from_path(host: str, remote_path: str) -> dict[str, str]:
        cleaned_path = remote_path.strip("/")
        parts = cleaned_path.split("/") if cleaned_path else []
        owner = parts[0] if len(parts) >= 2 else (parts[0] if parts else "unknown")
        name = parts[-1] if parts else "repository"
        if name.endswith(".git"):
            name = name[:-4]
        return {
            "host": host,
            "owner": owner,
            "name": name,
            "path": cleaned_path,
            "remote": f"{host}/{cleaned_path}" if cleaned_path else host,
        }

    def repositories(self) -> list[Repository]:
        repositories: list[Repository] = []
        seen_paths: set[Path] = set()
        for root in self.watched_roots:
            root = root.expanduser().resolve()
            if not root.exists():
                continue
            for current_root, dirnames, _filenames in os.walk(root):
                current_path = Path(current_root)
                dirnames[:] = [name for name in dirnames if name != ".git"]
                if self._is_ignored(current_path, root):
                    continue
                if self._is_repository_root(current_path):
                    resolved = current_path.resolve()
                    if resolved not in seen_paths:
                        repositories.append(Repository(resolved))
                        seen_paths.add(resolved)
                    # Once a repository root is found, do not recurse into its children.
                    dirnames.clear()
        repositories.sort(key=lambda repository: (str(repository.path), repository.name))
        return repositories

    def _is_repository_root(self, path: Path) -> bool:
        return (path / ".git").exists()

    def _is_ignored(self, candidate_path: Path, root: Path) -> bool:
        try:
            relative_path = candidate_path.relative_to(root)
        except ValueError:
            relative_path = candidate_path
        relative_text = str(relative_path)
        return any(fnmatch(relative_text, pattern) for pattern in self.ignore_patterns)


@dataclass(slots=True, frozen=True)
class Repository:
    path: Path
    display_name: str | None = None

    @property
    def name(self) -> str:
        return self.display_name or self.path.name

    def status(self) -> RepositoryStatus:
        return RepositoryStatus.from_repository(self)

    def fetch(self, remote_name: str = "origin") -> FetchResult:
        from .executor import GitCommandExecutor
        import time

        started_at = time.perf_counter()
        try:
            completed = GitCommandExecutor.fetch(self.path, remote_name)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            output = "\n".join(value for value in (completed.stdout.strip(), completed.stderr.strip()) if value)
            updated_refs = tuple(line.strip() for line in output.splitlines() if line.strip())
            return FetchResult(repository=self, success=True, duration_ms=duration_ms, updated_refs=updated_refs)
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            return FetchResult(repository=self, success=False, error_message=str(exc), duration_ms=duration_ms)


@dataclass(slots=True, frozen=True)
class RepositoryStatus:
    repository: Repository
    current_branch: str
    head_sha: str
    tracking_branch: str | None
    ahead_count: int
    behind_count: int
    is_dirty: bool
    is_detached_head: bool
    last_commit_date: datetime

    @classmethod
    def from_repository(cls, repository: Repository) -> RepositoryStatus:
        from .executor import GitCommandExecutor

        current_branch = GitCommandExecutor.current_branch(repository.path)
        tracking_branch = GitCommandExecutor.tracking_branch(repository.path)
        ahead_count, behind_count = GitCommandExecutor.ahead_behind(repository.path, tracking_branch)
        last_commit_text = GitCommandExecutor.last_commit_date(repository.path)
        last_commit_date = datetime.fromisoformat(last_commit_text)
        return cls(
            repository=repository,
            current_branch=current_branch,
            head_sha=GitCommandExecutor.head_sha(repository.path),
            tracking_branch=tracking_branch,
            ahead_count=ahead_count,
            behind_count=behind_count,
            is_dirty=GitCommandExecutor.is_dirty(repository.path),
            is_detached_head=current_branch == "HEAD",
            last_commit_date=last_commit_date,
        )

    @property
    def is_up_to_date(self) -> bool:
        return self.behind_count == 0 and self.ahead_count == 0 and not self.is_dirty