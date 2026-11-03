#!/usr/bin/env python3
"""Read packaged extension assets and emit metadata/hashes, never browser state."""
import argparse
import hashlib
import json
from pathlib import Path
import re

SIGNALS = {
    "native_messaging": r"nativeMessaging|connectNative",
    "permission_modes": r"permissionMode|skip_all_permission_checks",
    "user_prompt_field": r"userSystemPrompt|SYSTEM_PROMPT",
    "remote_prompt_config": r"chrome_ext_system_prompt|chrome_ext_skip_perms_system_prompt",
    "account_creation_ui_notice": r"create accounts",
}


def inspect(root):
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy_path = root / "managed_schema.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path.exists() else {}
    components = []
    # Only shipped application bundles. Never inspect profile storage, cookies,
    # keychains, logs, conversations or extension local/session storage.
    for path in sorted((root / "assets").glob("*.js")):
        if path.is_symlink():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        signals = {name: len(re.findall(pattern, text, re.I)) for name, pattern in SIGNALS.items()}
        signals = {name: count for name, count in signals.items() if count}
        if signals:
            components.append({"file": path.relative_to(root).as_posix(), "bytes": len(data),
                               "sha256": hashlib.sha256(data).hexdigest(), "signals": signals})
    return {"extension_version": manifest.get("version"),
            "manifest_version": manifest.get("manifest_version"),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "background": manifest.get("background"),
            "permissions": manifest.get("permissions", []),
            "host_permissions": manifest.get("host_permissions", []),
            "managed_policy_keys": sorted(policy.get("properties", {})),
            "components": components,
            "interpretation": "Static signals only; not proof of an enabled setting or server-side behavior."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extension_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.extension_directory.expanduser()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
