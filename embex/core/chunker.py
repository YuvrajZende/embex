"""
Chunker — split file content into overlapping fixed-size line chunks.

Each chunk is a tuple of ``(text, chunk_index, start_line, end_line)``
where *start_line* and *end_line* are 1-based line numbers.
"""

from __future__ import annotations


def chunk_content(
    content: str,
    chunk_size: int = 200,
    overlap: int = 20,
) -> list[tuple[str, int, int, int]]:
    """Split *content* into overlapping line-based chunks.

    Parameters
    ----------
    content:
        Raw file content as a single string.
    chunk_size:
        Maximum number of *lines* per chunk.
    overlap:
        Number of lines to overlap between consecutive chunks.

    Returns
    -------
    list[tuple[str, int, int, int]]
        A list of ``(chunk_text, chunk_index, start_line, end_line)`` tuples
        where *start_line* and *end_line* are 1-based line numbers.
        Returns an empty list for empty content.
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    total = len(lines)

    if total == 0:
        return []

    chunks: list[tuple[str, int, int, int]] = []
    step = max(chunk_size - overlap, 1)
    idx = 0
    start = 0

    while start < total:
        end = min(start + chunk_size, total)
        chunk_text = "".join(lines[start:end])
        # start_line / end_line are 1-based
        chunks.append((chunk_text, idx, start + 1, end))
        idx += 1
        start += step
        # Avoid creating a tiny trailing chunk that is purely overlap
        if start < total and (total - start) <= overlap:
            chunk_text = "".join(lines[start:total])
            chunks.append((chunk_text, idx, start + 1, total))
            break

    return chunks
