from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(slots=True)
class GitCommandError(RuntimeError):
    repo_path: Path
    command: tuple[str, ...]
    stdout: str = ""
    stderr: str = ""

    def __str__(self) -> str:
        command = " ".join(self.command)
        details = self.stderr.strip() or self.stdout.strip() or "git command failed"
        return f"{self.repo_path}: git {command}: {details}"


class GitCommandExecutor:
    _instance: GitCommandExecutor | None = None

    def __new__(cls) -> GitCommandExecutor:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def instance(cls) -> GitCommandExecutor:
        return cls()

    @classmethod
    def run(cls, repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        command = ("git", *args)
        completed = subprocess.run(
            command,
            cwd=repo_path,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise GitCommandError(
                repo_path=repo_path,
                command=args,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return completed

    @classmethod
    def is_repository(cls, path: Path) -> bool:
        if not path.exists():
            return False
        try:
            cls.run(path, "rev-parse", "--is-inside-work-tree")
        except GitCommandError:
            return False
        return True

    @classmethod
    def current_branch(cls, repo_path: Path) -> str:
        return cls.run(repo_path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    @classmethod
    def head_sha(cls, repo_path: Path) -> str:
        return cls.run(repo_path, "rev-parse", "HEAD").stdout.strip()

    @classmethod
    def tracking_branch(cls, repo_path: Path) -> str | None:
        try:
            return cls.run(repo_path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").stdout.strip()
        except GitCommandError:
            return None

    @classmethod
    def ahead_behind(cls, repo_path: Path, tracking_branch: str | None) -> tuple[int, int]:
        if not tracking_branch:
            return 0, 0
        output = cls.run(repo_path, "rev-list", "--left-right", "--count", f"{tracking_branch}...HEAD").stdout.strip()
        behind_text, ahead_text = output.split()
        return int(ahead_text), int(behind_text)

    @classmethod
    def is_dirty(cls, repo_path: Path) -> bool:
        return bool(cls.run(repo_path, "status", "--porcelain").stdout.strip())

    @classmethod
    def last_commit_date(cls, repo_path: Path) -> str:
        return cls.run(repo_path, "log", "-1", "--format=%cI", "HEAD").stdout.strip()

    @classmethod
    def remote_url(cls, repo_path: Path, remote_name: str) -> str | None:
        try:
            return cls.run(repo_path, "remote", "get-url", remote_name).stdout.strip()
        except GitCommandError:
            return None

    @classmethod
    def fetch(cls, repo_path: Path, remote_name: str) -> subprocess.CompletedProcess[str]:
        return cls.run(repo_path, "fetch", "--prune", remote_name)

    @classmethod
    def clone(cls, remote: str, destination: Path) -> subprocess.CompletedProcess[str]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = ("git", "clone", remote, str(destination))
        completed = subprocess.run(
            command,
            cwd=destination.parent,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise GitCommandError(
                repo_path=destination.parent,
                command=("clone", remote, str(destination)),
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return completed

    @classmethod
    def delete_repo(cls, repo_path: Path) -> None:
        import shutil

        shutil.rmtree(repo_path)
