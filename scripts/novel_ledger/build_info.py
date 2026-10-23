"""Hash the installed executable and writing rules, excluding historical validation artifacts."""
from __future__ import annotations

from pathlib import Path
from .contracts import VERSION, digest


def fingerprint(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    code = [root / 'scripts' / 'novel.py', *sorted((root / 'scripts' / 'novel_ledger').glob('*.py'))]
    rules = [root / 'SKILL.md', *sorted((root / 'references').glob('*.md'))]

    def group(files):
        return digest({path.relative_to(root).as_posix(): digest(path.read_bytes().hex()) if path.is_file() else None
                       for path in files})

    return {'version': VERSION, 'engine_hash': group(code), 'rules_hash': group(rules)}
