"""
Chunker — splits file content into overlapping fixed-size line chunks.
"""


def chunk_content(content, chunk_size=200, overlap=20):
    """Split content into overlapping line-based chunks.

    Returns a list of (chunk_text, chunk_index, start_line, end_line) tuples.
    Line numbers are 1-based.
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    total = len(lines)

    if total == 0:
        return []

    chunks = []
    step = max(chunk_size - overlap, 1)
    idx = 0
    start = 0

    while start < total:
        end = min(start + chunk_size, total)
        chunk_text = "".join(lines[start:end])
        chunks.append((chunk_text, idx, start + 1, end))
        idx += 1
        start += step

        # Avoid tiny trailing chunk that's just overlap
        if start < total and (total - start) <= overlap:
            chunk_text = "".join(lines[start:total])
            chunks.append((chunk_text, idx, start + 1, total))
            break

    return chunks
