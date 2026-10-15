"""Local output locations, independent of the ledger's storage implementation."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from .contracts import require


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        temporary.write_text(content, encoding='utf-8')
        os.replace(str(temporary), str(path))
    finally:
        temporary.unlink(missing_ok=True)


class LocalWorkspace:
    """Own project files and protect storage paths supplied by the composition root.

    Protected names are deliberately opaque: a ledger adapter may use one file, several
    files, or an external service. Both symbolic links and existing hard links resolve
    to the same protected resource.
    """

    def __init__(self, project, protected_paths=()):
        self.project = Path(project).expanduser().resolve()
        self.protected_paths = tuple(
            (path if path.is_absolute() else self.project / path).resolve()
            for path in (Path(value).expanduser() for value in protected_paths)
        )

    def output_path(self, output, default):
        target = (Path(output).expanduser() if output else self.project / default).resolve()
        require(not any(self.same_path(target, protected) for protected in self.protected_paths),
                'output', '不能覆盖账本存储及其受保护文件。')
        return target

    def artifact_path(self, path):
        """Validate work-file aliases, retaining the final link as the write/remove target.

        Work files are owned by the controller. Rebuilding or retiring one replaces
        the directory entry, never the file a worker may have linked it to. Parent
        directories must remain inside the project before any write or deletion.
        Explicit export destinations continue to use output_path instead.
        """
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.project / candidate
        parent = candidate.parent.resolve()
        require(parent.is_relative_to(self.project), 'output', '工作文件的父目录不能指向项目外。')
        self.output_path(candidate, '')
        return parent / candidate.name

    def write_text(self, path, content):
        # Validate aliases without changing the caller's chosen directory entry.
        # Explicit exports already resolve their destination; owned artifacts must
        # retain the final link so atomic replacement never writes its target.
        target = Path(path).expanduser()
        self.output_path(target, '')
        atomic_write(target, content)

    def write_json(self, path, value):
        self.write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

    @staticmethod
    def same_path(left, right):
        left, right = Path(left).resolve(), Path(right).resolve()
        if left == right:
            return True
        try:
            return left.samefile(right)
        except OSError:
            return False
