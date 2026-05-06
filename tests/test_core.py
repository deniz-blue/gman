from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from gman import selectors
from gman.models import AppConfig


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=repo_path, check=True, text=True, capture_output=True)


class CoreModelTests(unittest.TestCase):
    def test_repository_status_and_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "sample-repo"
            repo_path.mkdir()
            run_git(repo_path, "init")
            run_git(repo_path, "config", "user.name", "Test User")
            run_git(repo_path, "config", "user.email", "test@example.com")
            (repo_path / "README.md").write_text("sample\n", encoding="utf-8")
            run_git(repo_path, "add", "README.md")
            run_git(repo_path, "commit", "-m", "initial commit")

            config = AppConfig(watched_roots=[Path(temp_dir)])
            repositories = config.repositories()

            self.assertEqual(len(repositories), 1)
            repository = repositories[0]
            self.assertEqual(repository.path, repo_path)
            self.assertEqual(repository.name, "sample-repo")

            status = repository.status()
            self.assertEqual(status.repository, repository)
            self.assertNotEqual(status.current_branch, "")
            self.assertFalse(status.is_dirty)
            self.assertFalse(status.is_detached_head)
            self.assertEqual(status.ahead_count, 0)
            self.assertEqual(status.behind_count, 0)
            self.assertTrue(status.head_sha)

    def test_repositories_does_not_descend_into_discovered_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outer_repo_path = Path(temp_dir) / "outer-repo"
            outer_repo_path.mkdir()
            run_git(outer_repo_path, "init")
            run_git(outer_repo_path, "config", "user.name", "Test User")
            run_git(outer_repo_path, "config", "user.email", "test@example.com")
            (outer_repo_path / "README.md").write_text("outer\n", encoding="utf-8")
            run_git(outer_repo_path, "add", "README.md")
            run_git(outer_repo_path, "commit", "-m", "outer commit")

            nested_repo_path = outer_repo_path / "nested-repo"
            nested_repo_path.mkdir()
            run_git(nested_repo_path, "init")
            run_git(nested_repo_path, "config", "user.name", "Test User")
            run_git(nested_repo_path, "config", "user.email", "test@example.com")
            (nested_repo_path / "README.md").write_text("nested\n", encoding="utf-8")
            run_git(nested_repo_path, "add", "README.md")
            run_git(nested_repo_path, "commit", "-m", "nested commit")

            config = AppConfig(watched_roots=[Path(temp_dir)])
            repositories = config.repositories()
            paths = {repository.path for repository in repositories}

            self.assertIn(outer_repo_path, paths)
            self.assertNotIn(nested_repo_path, paths)

    def test_clone_destination_template_tokens(self) -> None:
        config = AppConfig(clone_into="~/Source/Repos/{host}/{owner}/{name}")
        destination = config.clone_destination("git@github.com:octocat/hello-world.git")
        expected = (Path.home() / "Source" / "Repos" / "github.com" / "octocat" / "hello-world").resolve()
        self.assertEqual(destination, expected)

    def test_selector_api_exposes_explicit_operators(self) -> None:
        args = SimpleNamespace(
            name_contains="alpha",
            path_contains=None,
            under_root=[Path("/tmp")],
            sort_by="branch",
            descending=True,
            limit=1,
            status=False,
            dirty=False,
            clean=False,
        )

        repository_filters = selectors.repository_filters_from_args(args)
        repository_sort = selectors.repository_sort_from_args(args)
        status_sort = selectors.status_sort_from_args(args)

        repositories = [selectors.Repository(Path("/tmp/alpha-repo")), selectors.Repository(Path("/tmp/beta-repo"))]
        filtered = selectors.apply_operators(repositories, repository_filters)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].name, "alpha-repo")
        self.assertEqual(repository_sort.sort_name, "path")
        self.assertEqual(status_sort.sort_name, "branch")
        self.assertTrue(selectors.requires_status(args))


if __name__ == "__main__":
    unittest.main()