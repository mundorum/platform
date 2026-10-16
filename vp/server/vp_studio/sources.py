"""
Reference documents an author gives the authoring assistant: plain text
out of PDF and TXT files, and the block of text sent to the LLM.
Pure Python — no Django imports.

Nothing here is stored: the browser keeps the extracted text while the
author works in the assistant and sends it back with each draft request.
"""
from __future__ import annotations

import io
import re
from pathlib import PurePath

MAX_FILES = 10
MAX_FILE_BYTES = 20 * 1024 * 1024
# Most source text one LLM request carries (all documents together, ~30k
# tokens). Longer documents are cut, each keeping a fair share.
MAX_SOURCE_CHARS = 120_000

TEXT_SUFFIXES = ('.txt', '.md')


class SourceError(ValueError):
    """A file that can't be used; the message is safe to show."""


def tidy(text: str) -> str:
    """Normalise extracted text: no NULs, no trailing spaces, at most one blank line."""
    text = text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _decode(data: bytes) -> str:
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('cp1252', errors='replace')


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):
            raise SourceError('The PDF is password-protected.')
        return '\n\n'.join(page.extract_text() or '' for page in reader.pages)
    except SourceError:
        raise
    except Exception as exc:  # pypdf raises assorted errors on damaged files
        raise SourceError('The PDF could not be read.') from exc


def extract_text(name: str, data: bytes) -> str:
    """The text of one uploaded file; raises SourceError for unusable files."""
    if len(data) > MAX_FILE_BYTES:
        raise SourceError(f'The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.')
    suffix = PurePath(name).suffix.lower()
    if suffix == '.pdf' or data[:5] == b'%PDF-':
        text = _pdf_text(data)
    elif suffix in TEXT_SUFFIXES:
        text = _decode(data)
    else:
        raise SourceError('Only PDF and TXT files can be used.')
    return tidy(text)


def word_count(text: str) -> int:
    return len(text.split())


def source_block(documents: list[dict], limit: int = MAX_SOURCE_CHARS) -> tuple[str, bool]:
    """The documents as one text for a prompt, at most `limit` characters of
    document text; returns (text, truncated). A document shorter than its
    fair share leaves the rest to the longer ones."""
    docs = [(str(d.get('name') or f'Document {i + 1}'), str(d.get('text') or ''))
            for i, d in enumerate(documents)]
    docs = [(name, text) for name, text in docs if text.strip()]
    budget, shares = limit, {}
    for left, i in enumerate(sorted(range(len(docs)), key=lambda i: len(docs[i][1]))):
        shares[i] = min(len(docs[i][1]), budget // (len(docs) - left))
        budget -= shares[i]
    truncated = False
    parts = []
    for i, (name, text) in enumerate(docs):
        if len(text) > shares[i]:
            text, truncated = text[:shares[i]].rstrip() + '\n[…]', True
        parts.append(f'=== {name} ===\n{text}')
    return '\n\n'.join(parts), truncated
