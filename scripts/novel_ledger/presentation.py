"""Local presentation adapter for task files, revision proposals and world views."""
from __future__ import annotations

from pathlib import Path

from . import bookpage, delivery
from .ports import PublicationReader
from .workspace import LocalWorkspace


class LocalPresentation:
    def __init__(self, repo: PublicationReader, workspace: LocalWorkspace, entry):
        self.repo = repo
        self.workspace = workspace
        self.entry = Path(entry)

    def task(self, task, baseline=None, compact=False, preserve_result=False):
        return delivery.materialize(self.repo, task, self.entry, baseline, compact,
                                    workspace=self.workspace, preserve_result=preserve_result)

    def revision_path(self, plan_hash):
        return str(self.workspace.artifact_path(self.workspace.project / 'work' / ('revision-' + plan_hash + '.json')))

    def revision(self, plan):
        path = self.revision_path(plan['plan_hash'])
        self.workspace.write_json(path, plan)
        return path

    def world(self):
        return delivery.export_world(self.repo, lambda repo: bookpage.live_shell(self.workspace.project, self.entry),
                                     workspace=self.workspace)

    def book(self):
        return bookpage.write(self.repo, workspace=self.workspace, entry=self.entry)

    def board(self, board):
        return delivery.write_board_card(self.workspace, board)

    def question(self, board):
        return delivery.write_question_card(self.workspace, board)

    def volume_board(self, board):
        return delivery.write_volume_board_card(self.workspace, board)

    def volume_question(self, board):
        return delivery.write_volume_question_card(self.workspace, board)

    def snapshot(self, boundary):
        return delivery.write_advance_snapshot(self.workspace, boundary)

    def retire(self, task_id):
        delivery.retire(self.workspace.project / 'work' / task_id, workspace=self.workspace)
