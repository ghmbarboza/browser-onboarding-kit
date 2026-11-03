import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class KitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="onboarding test ' ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.config = self.root / "config"
        self.bin_dir = self.root / "bin"
        self.config.mkdir()
        self.base = {"permissions": {"defaultMode": "manual", "deny": ["Read(.env)"]},
                     "env": {"EXAMPLE_TEST_VALUE": "private-test-fixture"},
                     "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}
        self.write_settings(self.base)
        self.original_text = "# Minhas instruções\nTexto original sem newline final"
        (self.config / "CLAUDE.md").write_text(self.original_text, encoding="utf-8")

    def write_settings(self, value):
        (self.config / "settings.json").write_text(json.dumps(value), encoding="utf-8")

    def settings(self):
        return json.loads((self.config / "settings.json").read_text())

    def run_install(self, *args, success=True):
        result = subprocess.run([sys.executable, str(ROOT / "install.py"),
                                 "--config-dir", str(self.config), "--bin-dir", str(self.bin_dir), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr + result.stdout)
        return result

    def test_install_repeat_and_uninstall_preserve_external_changes(self):
        self.run_install()
        first = self.settings()
        self.run_install()
        self.assertEqual(first, self.settings())
        self.assertEqual(first["permissions"], self.base["permissions"])
        self.assertEqual(first["env"], self.base["env"])
        self.assertEqual(len(first["hooks"]["UserPromptSubmit"]), 2)
        self.run_install("--check")
        data = self.settings()
        data["future_setting"] = {"preserve": True}
        data["hooks"]["SessionStart"].append({"hooks": [{"type": "command", "command": "echo added-later"}]})
        self.write_settings(data)
        with (self.config / "CLAUDE.md").open("a") as handle:
            handle.write("\nMais instruções depois da instalação.\n")
        self.run_install("--uninstall")
        result = self.settings()
        self.assertEqual(result["permissions"], self.base["permissions"])
        self.assertTrue(result["future_setting"]["preserve"])
        self.assertEqual(result["hooks"]["SessionStart"][0]["hooks"][0]["command"], "echo added-later")
        self.assertEqual(result["hooks"]["UserPromptSubmit"], self.base["hooks"]["UserPromptSubmit"])
        self.assertEqual((self.config / "CLAUDE.md").read_text(),
                         self.original_text + "\nMais instruções depois da instalação.\n")
        self.assertFalse((self.bin_dir / "onboarding-studio").exists())

    def test_fresh_install_uninstall_removes_only_created_files(self):
        (self.config / "settings.json").unlink()
        (self.config / "CLAUDE.md").unlink()
        self.run_install()
        self.run_install("--uninstall")
        self.assertFalse((self.config / "settings.json").exists())
        self.assertFalse((self.config / "CLAUDE.md").exists())
        self.run_install("--uninstall")

    def test_invalid_settings_leave_all_files_untouched(self):
        path = self.config / "settings.json"
        path.write_text("{broken")
        self.run_install(success=False)
        self.assertEqual(path.read_text(), "{broken")
        self.assertEqual((self.config / "CLAUDE.md").read_text(), self.original_text)
        self.assertFalse((self.config / "backups").exists())

    def test_unknown_skill_collision_leaves_settings_untouched(self):
        path = self.config / "skills/browser-onboarding/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("Outra skill já existente")
        before = (self.config / "settings.json").read_bytes()
        self.run_install(success=False)
        self.assertEqual((self.config / "settings.json").read_bytes(), before)
        self.assertEqual(path.read_text(), "Outra skill já existente")

    def test_update_rejects_edited_runtime_and_uninstall_preserves_it(self):
        self.run_install()
        path = self.config / "browser-onboarding-kit/context.md"
        path.write_text("Minhas modificações")
        self.run_install(success=False)
        self.run_install("--check", success=False)
        self.run_install("--uninstall")
        self.assertEqual(path.read_text(), "Minhas modificações")

    def test_symlink_is_not_replaced(self):
        path = self.config / "CLAUDE.md"
        target = self.root / "original.md"
        target.write_text("Preservar destino")
        path.unlink()
        path.symlink_to(target)
        self.run_install(success=False)
        self.assertTrue(path.is_symlink())
        self.assertEqual(target.read_text(), "Preservar destino")

    def test_backups_are_private(self):
        self.run_install()
        backups = list((self.config / "backups/browser-onboarding-kit").iterdir())
        self.assertTrue(backups)
        for directory in backups:
            self.assertEqual(directory.stat().st_mode & 0o077, 0)
            for path in directory.iterdir():
                self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_modified_manifest_cannot_remove_unmanaged_files(self):
        self.run_install()
        victim = self.root / "unrelated.txt"
        victim.write_bytes(b"preserve")
        manifest = self.config / "browser-onboarding-kit/installation.json"
        data = json.loads(manifest.read_text())
        data["files"][str(victim)] = installer.digest(victim.read_bytes())
        manifest.write_text(json.dumps(data))
        self.run_install("--uninstall", success=False)
        self.assertEqual(victim.read_bytes(), b"preserve")

    def test_incomplete_global_marker_blocks_install_without_partial_writes(self):
        path = self.config / "CLAUDE.md"
        path.write_text(self.original_text + installer.BEGIN + "unfinished")
        before = (self.config / "settings.json").read_bytes()
        self.run_install(success=False)
        self.assertEqual((self.config / "settings.json").read_bytes(), before)
        self.assertFalse((self.config / "browser-onboarding-kit/context.md").exists())

    def test_hook_handles_events_malformed_input_and_opt_out(self):
        self.run_install()
        hook = self.config / "browser-onboarding-kit/context_hook.py"
        environment = {k: v for k, v in os.environ.items() if k != "BROWSER_ONBOARDING_OFF"}
        for event in ("SessionStart", "UserPromptSubmit"):
            result = subprocess.run([sys.executable, str(hook)], input=json.dumps({"hook_event_name": event}),
                                    text=True, capture_output=True, check=True, env=environment)
            output = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual(output["hookEventName"], event)
            self.assertEqual(output["additionalContext"], (ROOT / "runtime/context.md").read_text())
        for payload in ("broken json", "[]", '{"hook_event_name":"Stop"}'):
            result = subprocess.run([sys.executable, str(hook)], input=payload,
                                    text=True, capture_output=True, check=True, env=environment)
            self.assertEqual(result.stdout, "")
        result = subprocess.run([sys.executable, str(hook)], input='{"hook_event_name":"SessionStart"}',
                                text=True, capture_output=True, check=True,
                                env={**environment, "BROWSER_ONBOARDING_OFF": "1"})
        self.assertEqual(result.stdout, "")

    def test_launcher_passes_chrome_context_and_resume_in_quoted_paths(self):
        self.run_install()
        fake = self.bin_dir / "claude"
        fake.write_text("#!/usr/bin/env python3\nimport json,sys,os\n"
                        "if '--help' in sys.argv: print('--system-prompt-snapshot'); sys.exit()\n"
                        "print(json.dumps({'args':sys.argv[1:],'cwd':os.getcwd()}))\n")
        fake.chmod(0o700)
        project = self.root / "projeto com espaços"
        project.mkdir()
        environment = {**os.environ, "PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]}
        wrapper = self.bin_dir / "onboarding-studio"
        result = subprocess.run([str(wrapper), str(project), "--continue"],
                                text=True, capture_output=True, check=True, env=environment)
        output = json.loads(result.stdout)
        self.assertEqual(output["cwd"], str(project))
        self.assertEqual(output["args"][0], "--chrome")
        self.assertEqual(output["args"][-1], "--continue")
        self.assertIn((ROOT / "runtime/context.md").read_text(), output["args"])
        self.assertEqual(output["args"][output["args"].index("--system-prompt-snapshot") + 1], "off")
        for args in ([str(project), "--no-chrome"], [str(Path.home())]):
            result = subprocess.run([str(wrapper), *args], text=True, capture_output=True, env=environment)
            self.assertNotEqual(result.returncode, 0)

    def test_rollback_restores_originals_after_write_failure(self):
        first, second = self.root / "first", self.root / "second"
        first.write_bytes(b"first-original")
        second.write_bytes(b"second-original")
        original_write = installer.atomic_write
        failed = False

        def fail_once(path, data, mode=0o600):
            nonlocal failed
            if path == second and not failed:
                failed = True
                raise OSError("simulated write failure")
            return original_write(path, data, mode)

        with patch.object(installer, "atomic_write", side_effect=fail_once):
            with self.assertRaises(OSError):
                installer.apply_changes({first: (b"changed", 0o600), second: (b"changed", 0o600)},
                                        self.root / "backup")
        self.assertEqual(first.read_bytes(), b"first-original")
        self.assertEqual(second.read_bytes(), b"second-original")

    def test_disabled_hooks_are_reported_without_changing_permission_mode(self):
        self.write_settings({**self.base, "disableAllHooks": True})
        self.run_install()
        self.run_install("--check", success=False)
        self.assertTrue(self.settings()["disableAllHooks"])
        self.assertEqual(self.settings()["permissions"]["defaultMode"], "manual")


if __name__ == "__main__":
    unittest.main()
