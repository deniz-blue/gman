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
from gman.models import AppConfig, Repository, RunResult


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=repo_path, check=True, text=True, capture_output=True)


class CliFilteringSortingTests(unittest.TestCase):
    def test_list_simplified_flags_and_shorthands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            beta = root / "beta-repo"
            alpha.mkdir()
            beta.mkdir()
            run_git(alpha, "init")
            run_git(beta, "init")

            config_path = root / "config.json"
            config_path.write_text(json.dumps({"watched_roots": [str(root)]}), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["-c", str(config_path), "list", "-n", "beta", "-s", "name", "-d", "-l", "1"])

            self.assertEqual(exit_code, 0)
            output_text = output.getvalue()
            self.assertIn("beta-repo", output_text)
            self.assertNotIn("alpha-repo", output_text)

    def test_run_command_executes_in_filtered_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            beta = root / "beta-repo"
            alpha.mkdir()
            beta.mkdir()
            run_git(alpha, "init")
            run_git(beta, "init")

            config_path = root / "config.json"
            config_path.write_text(json.dumps({"watched_roots": [str(root)]}), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "-c",
                        str(config_path),
                        "-o",
                        "json",
                        "run",
                        "-n",
                        "alpha",
                        "pwd",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["name"], "alpha-repo")
            self.assertTrue(payload[0]["success"])

    def test_run_command_returns_non_zero_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            alpha.mkdir()
            run_git(alpha, "init")

            config_path = root / "config.json"
            config_path.write_text(json.dumps({"watched_roots": [str(root)]}), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["-c", str(config_path), "run", "git not-a-real-subcommand"])

            self.assertEqual(exit_code, 1)
            self.assertIn("failed", output.getvalue())

    def test_fetch_uses_shared_run_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            alpha.mkdir()
            run_git(alpha, "init")

            config_path = root / "config.json"
            config_path.write_text(json.dumps({"watched_roots": [str(root)]}), encoding="utf-8")

            fake_result = RunResult(
                repository=Repository(alpha),
                command="git fetch --prune origin",
                success=True,
                exit_code=0,
                duration_ms=5,
                stdout="",
                stderr="",
            )

            with patch("gman.cli.run_repository_command", return_value=fake_result) as run_mock:
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = main(["-c", str(config_path), "fetch"])

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once()
            called_command = run_mock.call_args[0][1]
            self.assertEqual(called_command, "git fetch --prune origin")

    def test_run_command_fail_fast_stops_after_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            beta = root / "beta-repo"
            alpha.mkdir()
            beta.mkdir()
            run_git(alpha, "init")
            run_git(beta, "init")

            config_path = root / "config.json"
            config_path.write_text(json.dumps({"watched_roots": [str(root)]}), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "-c",
                        str(config_path),
                        "-o",
                        "json",
                        "run",
                        "--fail-fast",
                        "false",
                    ]
                )

            self.assertEqual(exit_code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(len(payload), 1)
            self.assertFalse(payload[0]["success"])

    def test_run_command_pipe_stdout_prints_command_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha = root / "alpha-repo"
            alpha.mkdir()
            run_git(alpha, "init")

            config_path = root / "config.json"
            config_path.write_text(json.dumps({"watched_roots": [str(root)]}), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["-c", str(config_path), "run", "--pipe", "echo hello-from-run"])

            self.assertEqual(exit_code, 0)
            self.assertIn("hello-from-run", output.getvalue())

    def test_list_pretty_hides_path_by_default(self) -> None:
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

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["-c", str(config_path), "list"])

            self.assertEqual(exit_code, 0)
            output_text = output.getvalue()
            self.assertIn("NAME", output_text)
            self.assertIn("alpha-repo", output_text)
            self.assertNotIn(str(alpha), output_text)

    def test_list_pretty_show_path_flag(self) -> None:
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

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["-c", str(config_path), "--show-path", "list"])

            self.assertEqual(exit_code, 0)
            output_text = output.getvalue()
            self.assertIn("PATH", output_text)
            self.assertIn("alpha-repo", output_text)

    def test_list_json_output(self) -> None:
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

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["-c", str(config_path), "-o", "json", "list"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["name"], "alpha-repo")

    def test_list_whitespace_output(self) -> None:
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

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["-c", str(config_path), "-o", "whitespace", "list"])

            self.assertEqual(exit_code, 0)
            first_line = output.getvalue().splitlines()[0]
            self.assertIn("\t", first_line)
            self.assertIn("alpha-repo", first_line)

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
                exit_code = main(["-c", str(config_path), "list", "--name", "beta"])

            self.assertEqual(exit_code, 0)
            output_text = output.getvalue()
            self.assertIn("beta-repo", output_text)
            self.assertNotIn("alpha-repo", output_text)

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
                        "--sort",
                        "name",
                        "--desc",
                        "--limit",
                        "1",
                    ]
                )

            self.assertEqual(exit_code, 0)
            output_text = output.getvalue()
            self.assertIn("beta-repo", output_text)
            self.assertNotIn("alpha-repo", output_text)

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
                    exit_code = main(["-c", str(config_path), "list"])

            self.assertEqual(exit_code, 0)
            output_text = output.getvalue()
            self.assertIn("alpha-repo", output_text)

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
                        "-c",
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
                        "-c",
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