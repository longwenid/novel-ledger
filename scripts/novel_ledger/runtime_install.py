"""Snapshot a complete skill installation without touching its source checkout or novel."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path

from .build_info import fingerprint
from .contracts import require

PARTS = ('README.md', 'SKILL.md', 'scripts', 'references', 'assets', 'agents', 'docs')
MANIFEST = 'runtime-manifest.json'


def build_at(root):
    # A selected release can have a different version literal from the installer.
    build = fingerprint(root)
    tree = ast.parse((root / 'scripts/novel_ledger/contracts.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets):
            build['version'] = ast.literal_eval(node.value)
            break
    return build


def _files(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*')) if path.is_file() and path.name != MANIFEST
            and '__pycache__' not in path.parts and path.suffix != '.pyc'}


def verify(root):
    root = Path(root).resolve()
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        require(False, 'runtime_install', '运行副本缺少有效清单；保留现场并重新选择完整发布版本。')
    require(not any(path.is_symlink() for path in root.rglob('*')), 'runtime_install',
            '固定副本中出现链接；请重新选择独立完整副本。')
    require(manifest.get('schema') == 'novel-ledger.runtime/1'
            and manifest.get('files') == _files(root) and manifest.get('build') == build_at(root),
            'engine_changed', '固定运行副本内容已改变；不还原开发目录或改写任务指纹。')
    return manifest


def _commit(source, ref):
    try:
        commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', '--verify',
                                           '--end-of-options', ref + '^{commit}'], stderr=subprocess.PIPE,
                                          text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        require(False, 'runtime_install', '无法读取所选Git发布版本；核对提交或从完整发布目录固定安装。')
    require(re.fullmatch(r'[a-f0-9]{40,64}', commit), 'runtime_install', '发布版本未解析为提交。')
    return commit


def pin(source, output, *, ref=None, expected=None, project=None):
    source = Path(source).resolve()
    target = Path(output).expanduser().resolve()
    require(not target.is_relative_to(source) and not source.is_relative_to(target),
            'runtime_install', '运行副本须放在技能开发目录之外。')
    if target.exists():
        manifest = verify(target)
        require(ref is None or manifest.get('source_commit') == _commit(source, ref),
                'runtime_install', '目标目录已固定另一发布来源；请选择新目录，不覆盖或忽略显式ref。')
        require(expected is None or manifest['build'] == expected, 'engine_changed',
                '已有运行副本不匹配待办任务的冻结构建；请选择另一目录或准确发布版本。')
        return _result(target, manifest, project, True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.novel-runtime-', dir=target.parent) as directory:
        staging = Path(directory) / 'runtime'
        staging.mkdir()
        commit = None
        if ref:
            commit = _commit(source, ref)
            try:
                archive = subprocess.check_output(['git', '-C', str(source), 'archive', '--format=tar', commit,
                                                   '--', *PARTS], stderr=subprocess.PIPE)
            except (OSError, subprocess.CalledProcessError):
                require(False, 'runtime_install', '无法读取所选Git发布版本；核对提交或从完整发布目录固定安装。')
            with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
                for member in stream.getmembers():
                    path = staging / member.name
                    require(path.resolve().is_relative_to(staging) and
                            (member.isfile() or member.isdir()), 'runtime_install',
                            '发布归档包含越界路径或链接，拒绝展开。')
                stream.extractall(staging)
        else:
            before = build_at(source)
            for name in PARTS:
                path = source / name
                if path.is_dir():
                    shutil.copytree(path, staging / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
                elif path.is_file():
                    shutil.copy2(path, staging / name)
            require(before == build_at(source) == build_at(staging), 'engine_changed',
                    '固定运行副本时开发源码发生变化；未发布副本，请重试或选择提交版本。')
        require((staging / 'scripts/novel.py').is_file() and (staging / 'SKILL.md').is_file(),
                'runtime_install', '所选版本缺少完整技能入口。')
        build = build_at(staging)
        require(expected is None or build == expected, 'engine_changed',
                '所选发布版本与待办任务指纹不符；不会重签任务或改动开发目录。',
                {'expected': expected, 'selected': build})
        manifest = {'schema': 'novel-ledger.runtime/1', 'build': build, 'source_commit': commit,
                    'files': _files(staging)}
        (staging / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # File modes guard accidental writes, not a malicious account with filesystem access.
        for path in staging.rglob('*'):
            if path.is_file():
                path.chmod(0o555 if path.stat().st_mode & stat.S_IXUSR else 0o444)
        require(not target.exists(), 'runtime_install', '目标目录已被创建，未覆盖；请核对后重试。')
        os.rename(staging, target)
    return _result(target, manifest, project, False)


def _result(root, manifest, project, reused):
    import sys
    command = [sys.executable, str(root / 'scripts/novel.py')]
    if project:
        command += ['--project', str(Path(project).resolve())]
    return {'runtime_root': str(root), 'entry': str(root / 'scripts/novel.py'),
            'build': manifest['build'], 'reused': reused,
            'commands': {name: command + [name] for name in ('status', 'advance')},
            'note': '后续以此入口作为ROOT；新派工commands使用该副本。文件只读不等于OS权限隔离。'}
