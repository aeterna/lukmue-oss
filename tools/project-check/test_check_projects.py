"""Tests for check_projects.py. Run the checker as a subprocess on temp trees."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "check_projects.py"


class CheckProjectsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def make_project(self, dir_name, folder, text=None, **overrides):
        """Write <root>/<dir_name>/<folder>/project.toml.

        Fields default to a valid private tool; pass None as a value to omit a field.
        """
        fields = {"name": folder, "type": "tool", "target": "main.py", "visibility": "private"}
        fields.update(overrides)
        fields = {key: value for key, value in fields.items() if value is not None}
        if text is None:
            text = "".join(f"{key} = {json.dumps(value)}\n" for key, value in fields.items())
        project = self.root / dir_name / folder
        project.mkdir(parents=True, exist_ok=True)
        (project / "project.toml").write_text(text, encoding="utf-8")
        return project

    def run_checker(self, *args):
        return subprocess.run(
            [sys.executable, str(CHECKER), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )

    def check(self, visibility="private", dirs=("projects",)):
        args = ["--visibility", visibility]
        for dir_name in dirs:
            args += ["--dir", dir_name]
        return self.run_checker(*args)

    def assertFails(self, result, expected_stderr_lines):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.splitlines(), expected_stderr_lines)

    def test_valid_private_project_passes(self):
        self.make_project("projects", "alpha")
        result = self.check("private")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok: 1 project(s)\n")
        self.assertEqual(result.stderr, "")

    def test_valid_public_project_passes(self):
        self.make_project("projects", "alpha-tool", type="mod", visibility="public")
        result = self.check("public")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok: 1 project(s)\n")

    def test_missing_manifest_reported(self):
        (self.root / "projects" / "alpha").mkdir(parents=True)
        self.assertFails(
            self.check(),
            ["projects/alpha/project.toml: missing project.toml"],
        )

    def test_invalid_toml_reported_without_traceback(self):
        self.make_project("projects", "alpha", text='name = "alpha"\ntype =\n')
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(
            lines[0].startswith("projects/alpha/project.toml: invalid TOML: "), lines[0]
        )

    def test_missing_field_reported(self):
        self.make_project("projects", "alpha", target=None)
        self.assertFails(
            self.check(),
            ["projects/alpha/project.toml: missing required field 'target'"],
        )

    def test_extra_field_reported(self):
        self.make_project("projects", "alpha", extra="x")
        self.assertFails(
            self.check(),
            ["projects/alpha/project.toml: unknown field 'extra'"],
        )

    def test_bad_name_reported(self):
        self.make_project("projects", "Bad_Name", name="Bad_Name")
        self.assertFails(
            self.check(),
            [
                "projects/Bad_Name/project.toml: field 'name' value 'Bad_Name' "
                "does not match pattern ^[a-z0-9]+(-[a-z0-9]+)*$"
            ],
        )

    def test_name_folder_mismatch_reported(self):
        self.make_project("projects", "alpha", name="beta")
        self.assertFails(
            self.check(),
            ["projects/alpha/project.toml: name 'beta' does not match folder name 'alpha'"],
        )

    def test_bad_enum_reported(self):
        self.make_project("projects", "alpha", type="app")
        self.assertFails(
            self.check(),
            [
                "projects/alpha/project.toml: field 'type' must be one of "
                "tool, mod, helper, other; got 'app'"
            ],
        )

    def test_empty_target_reported(self):
        self.make_project("projects", "alpha", target="")
        self.assertFails(
            self.check(),
            ["projects/alpha/project.toml: field 'target' must have length >= 1"],
        )

    def test_visibility_mismatch_reported(self):
        self.make_project("projects", "alpha", visibility="public")
        self.assertFails(
            self.check("private"),
            [
                "projects/alpha/project.toml: visibility 'public' does not match "
                "--visibility 'private'"
            ],
        )

    def test_public_helper_rejected(self):
        self.make_project("projects", "alpha", type="helper", visibility="public")
        self.assertFails(
            self.check("public"),
            ["projects/alpha/project.toml: type 'helper' is not allowed for public projects"],
        )

    def test_private_helper_accepted(self):
        self.make_project("projects", "alpha", type="helper")
        result = self.check("private")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok: 1 project(s)\n")

    def test_absent_dir_is_skipped(self):
        self.make_project("projects", "alpha")
        result = self.check(dirs=("missing", "projects"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok: 1 project(s)\n")

    def test_only_absent_dirs_gives_zero_projects(self):
        result = self.check(dirs=("missing",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok: 0 project(s)\n")

    def test_hidden_directories_skipped(self):
        self.make_project("projects", "alpha")
        # Hidden project folders with no manifest or a broken manifest must be ignored.
        (self.root / "projects" / ".hidden" / "broken").mkdir(parents=True)
        self.make_project("projects", ".cache", text="not = [valid\n")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok: 1 project(s)\n")

    def test_multiple_problems_all_reported(self):
        self.make_project(
            "projects", "alpha", name="Bad_Name", type="app", target="", visibility="public", extra=1
        )
        (self.root / "projects" / "beta").mkdir(parents=True)
        self.make_project("projects", "gamma", text='name = "gamma"\ntype =\n')
        result = self.check("public")
        self.assertEqual(result.returncode, 1, result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(
            lines[:5],
            [
                "projects/alpha/project.toml: unknown field 'extra'",
                "projects/alpha/project.toml: field 'name' value 'Bad_Name' "
                "does not match pattern ^[a-z0-9]+(-[a-z0-9]+)*$",
                "projects/alpha/project.toml: field 'type' must be one of "
                "tool, mod, helper, other; got 'app'",
                "projects/alpha/project.toml: field 'target' must have length >= 1",
                "projects/alpha/project.toml: name 'Bad_Name' does not match folder name 'alpha'",
            ],
        )
        self.assertEqual(lines[5], "projects/beta/project.toml: missing project.toml")
        self.assertTrue(
            lines[6].startswith("projects/gamma/project.toml: invalid TOML: "), lines[6]
        )
        self.assertEqual(len(lines), 7, lines)
        self.assertEqual(result.stdout, "")

    def test_bad_cli_arguments_exit_2(self):
        root = str(self.root)
        cases = {
            "missing --root": ["--visibility", "private", "--dir", "projects"],
            "missing --visibility": ["--root", root, "--dir", "projects"],
            "invalid --visibility": ["--root", root, "--visibility", "secret", "--dir", "projects"],
            "missing --dir": ["--root", root, "--visibility", "private"],
        }
        for label, args in cases.items():
            with self.subTest(label):
                # Invoke the checker with exactly these arguments (no implicit --root).
                result = subprocess.run(
                    [sys.executable, str(CHECKER), *args],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
