"""Read-only publication queries shared by derived views and exports."""
from __future__ import annotations

from .ports import PublicationReader
from .verification import VerificationService


def publication(repo: PublicationReader):
    book = repo.load()
    if book['status'] == 'completed' and book.get('completion_snapshot'):
        snapshot = VerificationService(repo).snapshot(book['completion_snapshot'])
        return snapshot['book'], snapshot['chapters']
    return book, repo.headers(book['branch'])
