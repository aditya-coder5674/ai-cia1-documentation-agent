"""Local text knowledge base for the documentation assistant.

This is a lightweight, dependency-free retrieval layer. It uses TF-IDF cosine
similarity so the complete knowledge base remains local and easy to explain.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass
class Chunk:
    source: str
    text: str


def tokenize(text: str) -> list[str]:
    return [x.lower() for x in _TOKEN_RE.findall(text)]


def load_text_files(folder: str | Path, uploaded: Iterable[tuple[str, str]] = ()) -> list[Chunk]:
    """Load .txt files from a local folder plus optional uploaded text files."""
    chunks: list[Chunk] = []
    root = Path(folder)
    if root.exists():
        for path in sorted(root.rglob("*.txt")):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            chunks.extend(split_into_chunks(text, str(path)))
    for name, text in uploaded:
        chunks.extend(split_into_chunks(text, name))
    return chunks


def split_into_chunks(text: str, source: str, words_per_chunk: int = 180, overlap: int = 35) -> list[Chunk]:
    words = text.split()
    if not words:
        return []
    result: list[Chunk] = []
    step = max(1, words_per_chunk - overlap)
    for start in range(0, len(words), step):
        part = " ".join(words[start:start + words_per_chunk]).strip()
        if part:
            result.append(Chunk(source, part))
        if start + words_per_chunk >= len(words):
            break
    return result


def retrieve(query: str, chunks: list[Chunk], top_k: int = 5) -> list[tuple[Chunk, float]]:
    """Return the most relevant chunks using local TF-IDF cosine similarity."""
    if not chunks:
        return []
    documents = [tokenize(c.text) for c in chunks]
    query_terms = tokenize(query)
    if not query_terms:
        return []
    vocabulary = set(query_terms)
    for terms in documents:
        vocabulary.update(terms)
    idf: dict[str, float] = {}
    for term in vocabulary:
        count = sum(term in terms for terms in documents)
        idf[term] = math.log((1 + len(documents)) / (1 + count)) + 1

    def vector(terms: list[str]) -> dict[str, float]:
        counts: dict[str, int] = {}
        for term in terms:
            counts[term] = counts.get(term, 0) + 1
        return {term: (count / len(terms)) * idf[term] for term, count in counts.items()}

    q = vector(query_terms)
    q_norm = math.sqrt(sum(value * value for value in q.values())) or 1.0
    scored: list[tuple[Chunk, float]] = []
    for chunk, terms in zip(chunks, documents):
        v = vector(terms)
        dot = sum(q.get(term, 0.0) * value for term, value in v.items())
        norm = math.sqrt(sum(value * value for value in v.values())) or 1.0
        score = dot / (q_norm * norm)
        if score > 0:
            scored.append((chunk, score))
    return sorted(scored, key=lambda item: item[1], reverse=True)[:top_k]


def format_context(matches: list[tuple[Chunk, float]]) -> str:
    return "\n\n---\n\n".join(
        f"SOURCE: {chunk.source}\nRELEVANCE: {score:.2f}\n{chunk.text}"
        for chunk, score in matches
    )
