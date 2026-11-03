#!/usr/bin/env python3
"""Launch the installed Claude CLI with Chrome and fresh local context."""
import os
from pathlib import Path
import shutil
import sys


def main():
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help"}:
        print("Uso: onboarding-studio [pasta] [opções/prompt do Claude]\n"
              "Exemplo: onboarding-studio ./meu-projeto --continue\n"
              "Sem pasta: usa o diretório atual. Sempre ativa --chrome.")
        return
    if args and Path(args[0]).expanduser().is_dir():
        os.chdir(Path(args.pop(0)).expanduser())
    if Path.cwd() in {Path.home().resolve(), Path("/")}:
        raise SystemExit("Abra uma pasta de projeto antes de iniciar o agente.")
    if "--no-chrome" in args:
        raise SystemExit("Este launcher requer Claude in Chrome; remova --no-chrome.")
    if any(a in {"--bare", "--safe-mode"} for a in args):
        raise SystemExit("Este modo desativa parte da instalação; use o CLI diretamente para diagnóstico.")
    cli = shutil.which("claude")
    if not cli:
        raise SystemExit("Claude Code não encontrado no PATH.")
    context = Path(__file__).with_name("context.md")
    if not context.is_file():
        raise SystemExit("Contexto ausente; execute o instalador novamente.")
    # Older CLIs may lack the snapshot switch. Detect the public local flag.
    import subprocess
    help_text = subprocess.run([cli, "--help"], capture_output=True, text=True,
                               check=True, timeout=15).stdout
    flags = ["--chrome", "--append-system-prompt", context.read_text(encoding="utf-8")]
    if "--system-prompt-snapshot" in help_text:
        flags += ["--system-prompt-snapshot", "off"]
    os.execv(cli, [cli, *flags, *args])


if __name__ == "__main__":
    main()
