"""Выгрузка экспорта сессии агента (Claude Code, формат jsonl) в docs/agent-session/.

Берёт штатный транскрипт Claude Code и вырезает из него e-mail адреса,
чтобы экспорт можно было передать проверяющим (ТЗ, «Что мы ожидаем от вас», п. 3).

Использование:
    python3 tools/export_agent_session.py [путь_к_транскрипту.jsonl ...]

Без аргументов ищет транскрипты в ~/.claude/projects/.
"""
import re
import sys
from pathlib import Path

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Служебные адреса, которые не являются личными данными.
KEEP = {"noreply@anthropic.com"}
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "agent-session"


def redact(line: str) -> str:
    return EMAIL.sub(lambda m: m.group(0) if m.group(0) in KEEP else "<email скрыт>", line)


def main() -> None:
    sources = [Path(p) for p in sys.argv[1:]] or sorted(
        (Path.home() / ".claude" / "projects").glob("*/*.jsonl")
    )
    if not sources:
        sys.exit("Транскрипты не найдены")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for src in sources:
        dst = OUT_DIR / src.name
        with src.open(encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
            for line in fin:
                fout.write(redact(line))
        print(f"{src} -> {dst}")


if __name__ == "__main__":
    main()
