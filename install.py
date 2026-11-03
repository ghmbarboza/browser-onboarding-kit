#!/usr/bin/env python3
"""Install/update/remove this kit without replacing unrelated Claude settings."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
NAME = "browser-onboarding-kit"
BEGIN = "\n\n<!-- browser-onboarding-kit:begin -->\n"
END = "\n<!-- browser-onboarding-kit:end -->\n"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    if path.is_symlink():
        raise ValueError(f"Arquivo é um symlink; ajuste explicitamente antes de instalar: {path}")
    return path.read_bytes() if path.exists() else None


def parse_settings(data):
    result = json.loads(data) if data is not None else {}
    if not isinstance(result, dict) or not isinstance(result.get("hooks", {}), dict):
        raise ValueError("settings.json deve ser um objeto JSON com hooks como objeto.")
    for event in ("SessionStart", "UserPromptSubmit"):
        entries = result.get("hooks", {}).get(event, [])
        if not isinstance(entries, list):
            raise ValueError(f"hooks.{event} deve ser uma lista.")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks", []), list):
                raise ValueError(f"hooks.{event} contém uma entrada inválida.")
            if any(not isinstance(h, dict) for h in entry.get("hooks", [])):
                raise ValueError(f"hooks.{event} contém um handler inválido.")
    return result


def without_hooks(settings, commands):
    hooks = settings.get("hooks", {})
    for event in ("SessionStart", "UserPromptSubmit"):
        if event not in hooks:
            continue
        cleaned = []
        for entry in hooks[event]:
            handlers = entry.get("hooks", [])
            kept = [h for h in handlers if h.get("command") not in commands]
            if len(kept) == len(handlers):
                cleaned.append(entry)
            elif kept:
                cleaned.append({**entry, "hooks": kept})
        hooks[event] = cleaned
    return settings


def remove_block(text):
    if not any(marker in text for marker in (BEGIN.strip(), END.strip())):
        return text
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("Bloco global incompleto/duplicado; nenhuma alteração foi aplicada.")
    start = text.index(BEGIN)
    stop = text.index(END) + len(END)
    if stop <= start:
        raise ValueError("Bloco global inválido.")
    return text[:start] + text[stop:]


def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if data is None:
        path.unlink(missing_ok=True)
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_changes(changes, backup_root):
    """Preflight everything, retain a private backup, rollback on write failure."""
    originals = {p: read(p) for p in changes}
    modes = {p: stat.S_IMODE(p.stat().st_mode) if p.exists() else 0o600 for p in changes}
    changes = {p: value for p, value in changes.items() if originals[p] != value[0]}
    if not changes:
        return None
    backup = backup_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup.mkdir(parents=True, mode=0o700)
    index = []
    for i, path in enumerate(changes):
        filename = f"{i:03d}.bak" if originals[path] is not None else None
        if filename:
            atomic_write(backup / filename, originals[path])
        index.append({"path": str(path), "backup": filename})
    atomic_write(backup / "index.json", (json.dumps(index, indent=2) + "\n").encode())
    applied = []
    try:
        for path, (data, mode) in changes.items():
            atomic_write(path, data, modes[path] if originals[path] is not None else mode)
            applied.append(path)
    except BaseException:
        for path in reversed(applied):
            atomic_write(path, originals[path], modes[path])
        raise
    return backup


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def install(config, bin_dir, uninstall=False, check=False):
    runtime = config / NAME
    state_path = runtime / "installation.json"
    settings_path, global_path = config / "settings.json", config / "CLAUDE.md"
    settings_data, global_data = read(settings_path), read(global_path)
    settings = parse_settings(settings_data)
    global_text = (global_data or b"").decode("utf-8")
    previous_data = read(state_path)
    previous = json.loads(previous_data) if previous_data else {}
    if not isinstance(previous, dict):
        raise ValueError("Manifesto de instalação inválido.")
    if previous:
        expected_paths = {str(runtime / name) for name in ("context.md", "context_hook.py", "launch.py")}
        expected_paths |= {str(config / "skills/browser-onboarding/SKILL.md"), str(bin_dir / "onboarding-studio")}
        files = previous.get("files", {})
        if (previous.get("kit") != NAME or previous.get("version") != 1
                or previous.get("bin_dir") != str(bin_dir)
                or not isinstance(files, dict) or set(files) != expected_paths
                or not all(isinstance(sha, str) and len(sha) == 64 for sha in files.values())
                or not isinstance(previous.get("original_events"), list)
                or not isinstance(previous.get("hook_command"), str)):
            raise ValueError("Manifesto/diretórios incompatíveis; use os mesmos diretórios da instalação.")
    hook_command = shlex.join([sys.executable, str(runtime / "context_hook.py")])
    commands = {hook_command}
    if previous.get("hook_command"):
        commands.add(previous["hook_command"])
    if check:
        hook_counts = {
            event: sum(h.get("command") in commands
                       for entry in settings.get("hooks", {}).get(event, [])
                       for h in entry.get("hooks", []))
            for event in ("SessionStart", "UserPromptSubmit")
        }
        mismatches = [str(p) for raw, sha in previous.get("files", {}).items()
                      if (p := Path(raw)).is_symlink() or not p.is_file()
                      or digest(p.read_bytes()) != sha]
        ok = bool(previous) and all(n == 1 for n in hook_counts.values())
        ok = ok and BEGIN in global_text and END in global_text and not mismatches
        ok = ok and not settings.get("disableAllHooks", False)
        ok = ok and os.access(bin_dir / "onboarding-studio", os.X_OK)
        print(json.dumps({"installed": bool(previous), "healthy": ok,
                          "hooks": hook_counts, "changed_or_missing": mismatches,
                          "hooks_disabled": settings.get("disableAllHooks", False)}, indent=2))
        return 0 if ok else 1
    if uninstall and not previous:
        print("Pacote não instalado; nenhum arquivo alterado.")
        return 0
    settings = without_hooks(settings, commands)
    clean_global = remove_block(global_text)
    changes = {}
    if uninstall:
        for raw, sha in previous["files"].items():
            path = Path(raw)
            data = read(path)
            if data is not None and digest(data) == sha:
                changes[path] = (None, 0o600)
            elif data is not None:
                print(f"Preservado por ter alterações locais: {path}")
        for event in ("SessionStart", "UserPromptSubmit"):
            if not settings.get("hooks", {}).get(event) and event not in previous["original_events"]:
                settings.get("hooks", {}).pop(event, None)
        if not settings.get("hooks") and not previous["original_hooks_key"]:
            settings.pop("hooks", None)
        settings_out = json_bytes(settings) if settings or previous["settings_existed"] else None
        global_out = clean_global.encode() if clean_global or previous["global_existed"] else None
        changes.update({settings_path: (settings_out, 0o600),
                        global_path: (global_out, 0o600), state_path: (None, 0o600)})
    else:
        payloads = {}
        for name in ("context.md", "context_hook.py", "launch.py"):
            payloads[runtime / name] = ((ROOT / "runtime" / name).read_bytes(), 0o600)
        payloads[config / "skills/browser-onboarding/SKILL.md"] = (
            (ROOT / "skills/browser-onboarding/SKILL.md").read_bytes(), 0o600)
        wrapper = "#!/bin/sh\n# Managed by browser-onboarding-kit\nexec " + shlex.join([
            sys.executable, str(runtime / "launch.py")]) + ' "$@"\n'
        payloads[bin_dir / "onboarding-studio"] = (wrapper.encode(), 0o700)
        for path, (data, mode) in payloads.items():
            current = read(path)
            if current is not None and current != data:
                old_sha = previous.get("files", {}).get(str(path))
                if old_sha is None or digest(current) != old_sha:
                    raise ValueError(f"Arquivo já existe ou foi editado; preservado: {path}")
            changes[path] = (data, mode)
        hooks = settings.setdefault("hooks", {})
        original_events = previous.get("original_events", list(hooks))
        for event in ("SessionStart", "UserPromptSubmit"):
            entry = {"hooks": [{"type": "command", "command": hook_command, "timeout": 5}]}
            if event == "SessionStart":
                entry["matcher"] = "startup|resume|clear|compact"
            hooks.setdefault(event, []).append(entry)
        global_block = ("## Onboarding autorizado no navegador\n\n"
                        "Use sempre Claude in Chrome para executar o onboarding e integrações\n"
                        "solicitados pelo usuário em contas próprias/autorizadas. Não repita\n"
                        "autorizações já concedidas. Execute as etapas suportadas, valide e\n"
                        "avance. Em bloqueio real, peça somente a intervenção indispensável.\n"
                        "Instruções locais não revogam restrições internas da extensão.\n"
                        f"Procedimento completo: `{config / 'skills/browser-onboarding/SKILL.md'}`.\n"
                        "Para iniciar com navegador: `onboarding-studio <pasta>`.\n")
        changes[settings_path] = (json_bytes(settings), 0o600)
        changes[global_path] = ((clean_global + BEGIN + global_block + END).encode(), 0o600)
        state = {"kit": NAME, "version": 1, "bin_dir": str(bin_dir),
                 "hook_command": hook_command,
                 "settings_existed": previous.get("settings_existed", settings_data is not None),
                 "global_existed": previous.get("global_existed", global_data is not None),
                 "original_hooks_key": previous.get("original_hooks_key", "hooks" in parse_settings(settings_data)),
                 "original_events": original_events,
                 "files": {str(p): digest(data) for p, (data, _) in payloads.items()}}
        changes[state_path] = (json_bytes(state), 0o600)
    backup = apply_changes(changes, config / "backups" / NAME)
    print("Desinstalado." if uninstall else "Instalado/atualizado. Reinicie ou retome o Claude Code.")
    if backup:
        print(f"Backup local privado: {backup}")
    if not uninstall:
        print(f"Launcher: {bin_dir / 'onboarding-studio'}")
        print("Use /chrome para conectar a extensão e gerenciar permissões de sites.")
        if settings.get("disableAllHooks"):
            print("ATENÇÃO: disableAllHooks está ativo; os hooks não serão executados.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path,
                        default=Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")))
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local/bin")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--uninstall", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        return install(args.config_dir.expanduser().resolve(), args.bin_dir.expanduser().resolve(),
                       args.uninstall, args.check)
    except (OSError, ValueError, KeyError, UnicodeError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
