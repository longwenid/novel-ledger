"""Read-only publication queries shared by derived views and exports."""
from __future__ import annotations

from .ports import PublicationReader


def publication(repo: PublicationReader):
    book = repo.load()
    if book['status'] == 'completed' and book.get('completion_snapshot'):
        snapshot = repo.read_document(book['completion_snapshot'])
        return snapshot['book'], snapshot['chapters']
    return book, repo.headers(book['branch'])
