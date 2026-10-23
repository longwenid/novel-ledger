"""Unattended progression: the engine's own wait loop for hosts that execute workers externally.

The controller's loop used to live in the host session: dispatch a worker, then poll `status` on
a timer, where every poll was a full-context model call. A real unattended run spent 121 such
polls — 11.5 hours of wall time — waiting for workers that needed no supervision, and the host's
context grew on every one of them. This module owns the waiting instead: Python sleeps, the
controller lease is renewed, and the caller is returned to only when something actually needs it.
"""
from __future__ import annotations

import time
from .contracts import require, text

# The controller lease defaults to 300 seconds; renewing well inside that keeps a long wait from
# looking like an abandoned run to the next advance.
RENEW_EVERY = 30.0


def watch(app, owner, steps=1, poll=20.0, idle_limit=1800.0, sleep=time.sleep, now=time.monotonic,
          on_dispatch=None):
    """Advance whenever the project can move, waiting quietly while a worker holds the task.

    Each round advances once, journals the dispatch through the optional callback, then waits for
    that task's external submission by polling its status — no host inference happens while
    waiting. The loop returns to the caller exactly when the caller has something to do:

    - the round budget is spent and the next dispatch is ready (`task_ready`, with the task);
    - the project stops itself: an author decision, a pause, a completion or revision boundary,
      a resync — returned untouched, because those belong to the controller or the author;
    - a worker goes silent past `idle_limit` (`idle`), which is a fact the caller must act on.

    `steps` counts dispatch-and-wait rounds; one further advance fetches the handoff to act on,
    so the host's per-task cost is one call to this command, not a polling sequence. `steps=0`
    loops until a stop point — pair it with an external dispatcher reading the journal.
    """
    require(text(owner), 'watch', '持续监督需要主控 owner（run 命令返回的 owner）。')
    require(type(steps) is int and steps >= 0, 'watch', 'steps 须为非负整数（0 表示一直到停止点）。')
    require(poll > 0 and idle_limit > 0, 'watch', 'poll 与 idle-limit 须为正数秒。')
    rounds, waited = 0, []
    while True:
        handoff = app.advance(owner=owner, compact=True,
                              wait_pending=not steps or rounds < steps)
        action = handoff.get('action')
        if action not in ('task_ready', 'wait_for_submit', 'wait_for_batch'):
            return {**handoff, 'dispatched': waited,
                    'watch_note': 'watch 在此停下：这一步需要主控或作者处理，处理后再次运行 watch 继续。'}
        if steps and rounds >= steps:
            return {**handoff, 'dispatched': waited,
                    'watch_note': '下一派工已就绪，按 task 派出 Worker 后再运行 watch 等它完成。'}
        task = handoff['task']
        row = {'task_id': task['task_id'], 'stage': task.get('stage'),
               'chapter': task.get('chapter'), 'scope': task.get('scope')}
        waited.append(row)
        if on_dispatch:
            on_dispatch(row)
        idle_at, renew_at = now() + idle_limit, now() + RENEW_EVERY
        cursor = task['task_id']
        while True:
            current = app.task_status(task['task_id'])
            review = current.get('continuity')
            if review and (current['status'] == 'pending' or current.get('batch_active')):
                return {'action': 'review_complete' if review['phase'] == 'done' else 'review_required',
                        'task_id': current.get('batch_task') or task['task_id'], 'review': review, 'dispatched': waited}
            if current.get('execution_blocked'):
                return {'action': 'worker_blocked', 'task_id': current.get('batch_task') or task['task_id'],
                        'recovery': current.get('recovery'), 'dispatched': waited,
                        'boundary': '技术执行已停止，由主控修复交接原因后 prepare-worker --reset-failures。'}
            if current['status'] != 'pending' and not current.get('batch_active'):
                break
            if current.get('batch_task') and current['batch_task'] != cursor:
                cursor, idle_at = current['batch_task'], now() + idle_limit
            moment = now()
            if moment >= idle_at:
                return {'action': 'idle', 'task_id': task['task_id'], 'dispatched': waited,
                        'idle_after': idle_limit,
                        'boundary': 'Worker 长时间未提交：确认执行者仍在，或按当前状态重新派工。'}
            if moment >= renew_at:
                app.renew(owner)
                renew_at = moment + RENEW_EVERY
            sleep(poll)
        rounds += 1
