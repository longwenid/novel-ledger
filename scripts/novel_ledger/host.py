"""Optional subprocess host adapter. A real model host must supply session isolation."""
from __future__ import annotations

import os
import contextlib
import subprocess
import time
import uuid
from pathlib import Path
from .contracts import require, text
from .ports import HostApplication


def step(app: HostApplication, command, owner=None, timeout=300):
    require(isinstance(command, list) and command and all(text(s) for s in command), 'host_command', '宿主命令须为 argv 字符串数组，不使用 shell。')
    require(type(timeout) is int and timeout > 0, 'host_timeout', '超时须为正整数。')
    handoff = app.advance(owner=owner)
    if handoff['action'] != 'task_ready':
        return handoff
    envelope = handoff['task']
    task = app.task_status(envelope['task_id'])
    if task['reviewer']:
        return {'action': 'resume_session_required', 'task_id': task['id'], 'session': task['reviewer'],
                'message': '冻结首读须沿原模型会话恢复；该通用宿主不证明会话恢复能力。'}
    transport = envelope.get('process')
    require(isinstance(transport, dict) and all(text(transport.get(key))
            for key in ('project_path', 'task_path', 'log_path')), 'host_transport',
            '此交付适配器未提供子进程宿主所需的文件传输能力。',
            {'recover': '使用提供 FileTaskTransport 的交付适配器，或由当前宿主直接执行任务。'})
    log_path = Path(transport['log_path'])
    session = 'host-' + uuid.uuid4().hex
    claim = app.claim(task['id'], session, timeout + 60)
    try:
        environment = {**os.environ, 'NOVEL_TASK_PATH': transport['task_path'], 'NOVEL_PROJECT': transport['project_path'],
                       'NOVEL_TASK_ID': task['id'], 'NOVEL_SESSION': session, 'NOVEL_EXECUTION_CLAIM': claim['token']}
        started = time.monotonic()
        renew_at = started + 30
        if owner:
            app.renew(owner, timeout + 60)
        with contextlib.ExitStack() as stack:
            try:
                # Replace the owned directory entry. Following an existing symlink or
                # truncating a hard link could otherwise change an unrelated file.
                log_path.unlink(missing_ok=True)
                stream = stack.enter_context(log_path.open('xb'))
                process = subprocess.Popen(command, env=environment, stdout=stream, stderr=subprocess.STDOUT, shell=False)
            except OSError as exc:
                return {'action': 'host_launch_failed', 'task_id': task['id'], 'message': str(exc), 'log': str(log_path)}
            try:
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        return {'action': 'host_timeout', 'task_id': task['id'], 'log': str(log_path)}
                    if owner and time.monotonic() >= renew_at:
                        app.renew(owner, timeout + 60)
                        renew_at = time.monotonic() + 30
                    time.sleep(0.2)
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
        current = app.task_status(task['id'])
        return {'action': 'worker_finished' if current['status'] == 'done' and process.returncode == 0 else 'needs_attention',
                'task_id': task['id'], 'exit_code': process.returncode, 'submitted': current['status'] == 'done', 'log': str(log_path)}
    finally:
        app.release_claim(task['id'], claim['token'])


def loop(app: HostApplication, command, owner, limit=100, timeout=300):
    require(text(owner) and type(limit) is int and limit > 0, 'host_loop', '持续执行需要主控 owner 和正整数步数上限。')
    last = None
    for _ in range(limit):
        last = step(app, command, owner, timeout)
        if last['action'] != 'worker_finished':
            return last
    return {'action': 'step_limit', 'last': last}
