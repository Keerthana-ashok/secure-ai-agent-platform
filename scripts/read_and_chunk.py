"""Read markdown docs and split them into text chunks.

Usage:
  python scripts/read_and_chunk.py

This script is intentionally simple for beginners:
- Reads all `.md` files from the `docs/` folder.
- Splits each file into paragraph-based chunks up to a character limit.
- Prints chunk metadata and the text.
"""

from pathlib import Path
from typing import List, Tuple


def read_markdown_files(folder: str) -> List[Tuple[Path, str]]:
    """Return a list of (path, text) for each .md file in `folder`."""
    p = Path(folder)
    files = list(p.glob("*.md"))
    result = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        result.append((f, text))
    return result


def split_into_chunks(text: str, max_chars: int = 500) -> List[str]:
    """Split `text` into chunks of at most `max_chars` characters.

    Strategy:
    - Split text into paragraphs (double-newline)
    - Accumulate paragraphs until adding the next would exceed `max_chars`
    - Start a new chunk when needed
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) + 1 <= max_chars or not current:
            current.append(para)
            current_len += len(para) + 1
        else:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = len(para) + 1

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def process_docs(folder: str = "docs", max_chars: int = 500):
    files = read_markdown_files(folder)
    all_chunks = []

    for path, text in files:
        chunks = split_into_chunks(text, max_chars=max_chars)
        for i, c in enumerate(chunks, start=1):
            meta = {"source": str(path.name), "index": i, "text_length": len(c)}
            all_chunks.append((meta, c))

    return all_chunks


if __name__ == "__main__":
    chunks = process_docs("docs", max_chars=500)
    print(f"Found {len(chunks)} chunks:\n")
    for meta, text in chunks:
        print("---")
        print(f"Source: {meta['source']}  Chunk: {meta['index']}  Length: {meta['text_length']}")
        print()
        print(text)
        print()
