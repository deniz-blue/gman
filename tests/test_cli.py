from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from gman.cli import main
from gman.models import AppConfig, Repository


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=repo_path, check=True, text=True, capture_output=True)


class CliFilteringSortingTests(unittest.TestCase):
    def test_list_name_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            beta = root / "beta-repo"
            alpha.mkdir()
            beta.mkdir()
            run_git(alpha, "init")
            run_git(beta, "init")

            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({"watched_roots": [str(root)]}),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--config", str(config_path), "list", "--name-contains", "beta"])

            self.assertEqual(exit_code, 0)
            lines = [line for line in output.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            self.assertIn("beta-repo", lines[0])

    def test_list_sort_descending_and_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            beta = root / "beta-repo"
            alpha.mkdir()
            beta.mkdir()
            run_git(alpha, "init")
            run_git(beta, "init")

            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({"watched_roots": [str(root)]}),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--config",
                        str(config_path),
                        "list",
                        "--sort-by",
                        "name",
                        "--descending",
                        "--limit",
                        "1",
                    ]
                )

            self.assertEqual(exit_code, 0)
            lines = [line for line in output.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            self.assertIn("beta-repo", lines[0])

    def test_list_without_status_does_not_compute_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            alpha.mkdir()
            run_git(alpha, "init")

            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({"watched_roots": [str(root)]}),
                encoding="utf-8",
            )

            with patch.object(Repository, "status", side_effect=AssertionError("status should not be called")):
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = main(["--config", str(config_path), "list"])

            self.assertEqual(exit_code, 0)
            lines = [line for line in output.getvalue().splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            self.assertIn("alpha-repo", lines[0])

    def test_clone_command_clones_and_runs_post_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source-repo"
            source.mkdir()
            run_git(source, "init")
            run_git(source, "config", "user.name", "Test User")
            run_git(source, "config", "user.email", "test@example.com")
            (source / "README.md").write_text("source\n", encoding="utf-8")
            run_git(source, "add", "README.md")
            run_git(source, "commit", "-m", "initial")

            clone_root = root / "clones"
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "watched_roots": [str(clone_root)],
                        "cloneInto": str(clone_root / "{name}"),
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--config",
                        str(config_path),
                        "clone",
                        str(source),
                        "python -c \"from pathlib import Path; Path('post_clone.txt').write_text('ok', encoding='utf-8')\"",
                    ]
                )

            self.assertEqual(exit_code, 0)
            destination = clone_root / "source-repo"
            self.assertTrue((destination / ".git").exists())
            self.assertEqual((destination / "post_clone.txt").read_text(encoding="utf-8"), "ok")

    def test_clone_command_uses_host_owner_name_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source-repo"
            source.mkdir()
            run_git(source, "init")
            run_git(source, "config", "user.name", "Test User")
            run_git(source, "config", "user.email", "test@example.com")
            (source / "README.md").write_text("source\n", encoding="utf-8")
            run_git(source, "add", "README.md")
            run_git(source, "commit", "-m", "initial")

            clone_root = root / "clones"
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "watched_roots": [str(clone_root)],
                        "cloneInto": str(clone_root / "{host}" / "{owner}" / "{name}"),
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--config",
                        str(config_path),
                        "clone",
                        f"file://{source}",
                    ]
                )

            self.assertEqual(exit_code, 0)
            destination = AppConfig.load(config_path).clone_destination(f"file://{source}")
            self.assertTrue((destination / ".git").exists())


if __name__ == "__main__":
    unittest.main()