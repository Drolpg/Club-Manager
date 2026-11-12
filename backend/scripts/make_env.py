"""Cria o .env da raiz a partir do .env.example, com segredos aleatórios.

Uso: `uv run python scripts/make_env.py` (dentro de backend/). Não sobrescreve um .env que já exista.
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    target = ROOT / ".env"
    if target.exists():
        print(f"{target} já existe; nada foi alterado.")
        return 0
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    content = content.replace("troque-esta-senha", secrets.token_urlsafe(18))
    content = content.replace("troque-por-uma-chave-longa-e-aleatoria", secrets.token_urlsafe(48))
    target.write_text(content, encoding="utf-8", newline="\n")
    print(f"{target} criado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
