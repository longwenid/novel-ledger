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
import sys
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


def _mismatch_details(source, target, expected, selected, project, ref, task):
    """Offer two explicit paths without treating a new install as upgrade approval."""
    entry = [sys.executable, str(source / 'scripts/novel.py')]
    project_args = ['--project', str(Path(project).resolve())] if project else ['--project', '<project>']
    identity = {name: (task or {}).get(name, '<' + name + '>') for name in ('task_id', 'input_hash')}
    prepare = entry + ['pin-engine', '--output', '<new-runtime-directory>']
    if ref:
        prepare += ['--ref', ref]
    return {
        'expected': expected, 'selected': selected, 'runtime_root': str(target),
        **(task or {}),
        'recovery_options': {
            'match_frozen_build': {
                'changes_task': False,
                'required_build': expected,
                'command_template': entry + project_args + [
                    'pin-engine', '--ref', '<verified-release>', '--output', '<new-runtime-directory>'],
                'instructions': '从准确发布记录确定与expected完全相同的提交，或使用已验证匹配的固定副本；'
                                '不扫描或猜测Git历史，不修改开发目录或旧任务指纹。'},
            'upgrade_frozen_task': {
                'requires_author_upgrade': True,
                'prepare_command_template': prepare,
                'recover_command_template': [sys.executable, '<new-runtime-directory>/scripts/novel.py',
                    *project_args, 'recover-engine', '--task', identity['task_id'],
                    '--input-hash', identity['input_hash'], '--source', '<actual-author-upgrade-authorization>'],
                'conditional_arguments': {
                    '--owner': '项目已有主控认领时携带当前owner。',
                    '--worker-stopped': '原任务有登记执行者时，核实其实际停止后才添加；租约过期不构成证明。'},
                'instructions': '先不带--project把选定新发布固定到新目录，再从返回entry执行准确待办的recover-engine。'
                                '创建固定副本不批准升级，也不取消任务；升级仍校验作者授权、执行者停止及宿主权限。'}},
    }


def pin(source, output, *, ref=None, expected=None, project=None, task=None):
    source = Path(source).resolve()
    target = Path(output).expanduser().resolve()
    require(not target.is_relative_to(source) and not source.is_relative_to(target),
            'runtime_install', '运行副本须放在技能开发目录之外。')
    if target.exists():
        manifest = verify(target)
        require(ref is None or manifest.get('source_commit') == _commit(source, ref),
                'runtime_install', '目标目录已固定另一发布来源；请选择新目录，不覆盖或忽略显式ref。')
        require(expected is None or manifest['build'] == expected, 'engine_changed',
                '已有运行副本不匹配待办任务的冻结构建；按recovery_options选择匹配发布或经授权升级。',
                _mismatch_details(source, target, expected, manifest['build'], project, ref, task))
        # Existing valid targets are deliberately reusable even after the development
        # tree changes. Make that selection visible instead of implying a fresh copy.
        try:
            source_build = manifest['build'] if ref else build_at(source)
        except (OSError, SyntaxError, ValueError):
            # A half-edited development tree must not prevent restoring a verified
            # frozen target. Its comparison is unknown, never silently successful.
            source_build = None
        return _result(target, manifest, project, True, source_build)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.novel-runtime-', dir=target.parent) as directory:
        staging = Path(directory) / 'runtime'
        staging.mkdir()
        commit = None
        if ref:
            commit = _commit(source, ref)
            try:
                # Optional installation directories need not exist in every release.
                # Git archive rejects a missing explicit pathspec instead of skipping it.
                tracked = subprocess.check_output(['git', '-C', str(source), 'ls-tree', '-z', '--name-only',
                                                   commit, '--', *PARTS], stderr=subprocess.PIPE)
                parts = [name for name in tracked.decode('utf-8').split('\0') if name in PARTS]
                require(parts, 'runtime_install', '所选版本没有技能发布文件。')
                # Force archive bytes exactly as committed: host-level autocrlf/text
                # attributes would otherwise smear CRLF into the frozen copy and
                # break the engine fingerprint on Windows default git installs.
                archive = subprocess.check_output(['git', '-C', str(source), '-c', 'core.autocrlf=false',
                                                   '-c', 'core.eol=lf', '-c', 'core.attributesFile=',
                                                   'archive', '--format=tar', commit,
                                                   '--', *parts], stderr=subprocess.PIPE)
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
                '所选发布版本与待办任务指纹不符；按recovery_options选择匹配发布或经授权升级。',
                _mismatch_details(source, target, expected, build, project, ref, task))
        manifest = {'schema': 'novel-ledger.runtime/1', 'build': build, 'source_commit': commit,
                    'files': _files(staging)}
        (staging / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # File modes guard accidental writes, not a malicious account with filesystem access.
        for path in staging.rglob('*'):
            if path.is_file():
                path.chmod(0o555 if path.stat().st_mode & stat.S_IXUSR else 0o444)
        require(not target.exists(), 'runtime_install', '目标目录已被创建，未覆盖；请核对后重试。')
        os.rename(staging, target)
    return _result(target, manifest, project, False, manifest['build'])


def _result(root, manifest, project, reused, source_build):
    command = [sys.executable, str(root / 'scripts/novel.py')]
    if project:
        command += ['--project', str(Path(project).resolve())]
    source_matches = source_build == manifest['build'] if source_build is not None else None
    note = '后续以此入口作为ROOT；新派工commands使用该副本。文件只读不等于OS权限隔离。'
    if source_matches is None:
        note += '未能读取当前开发源码构建；本次仅复用已核验的固定副本，未发布当前源码。'
    elif not source_matches:
        note += '复用了已有固定构建，未复制当前开发源码；若要发布当前源码，请使用新目录并单独完成受控升级。'
    return {'runtime_root': str(root), 'entry': str(root / 'scripts/novel.py'),
            'build': manifest['build'], 'reused': reused,
            'source_build': source_build, 'source_matches_runtime': source_matches,
            'commands': {name: command + [name] for name in ('status', 'advance')},
            'note': note}
