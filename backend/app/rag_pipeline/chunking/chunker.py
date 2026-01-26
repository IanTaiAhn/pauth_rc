# chunking/chunker.py
from pathlib import Path
import re
from typing import List, Dict


def sentence_split(text: str) -> List[str]:
    # Very simple sentence splitter; replace with nltk if desired
    toks = re.split(r'(?<=[.!?])\s+', text)
    return [t.strip() for t in toks if t.strip()]

def chunk_text(
    text: str,
    tokenizer,
    max_tokens: int = 400,
    overlap: int = 100,
    min_chunk_tokens: int = 150
):
    """
    Chunk text by sentence boundaries with token-accurate sizing,
    token-based overlap, whitespace normalization, and minimum chunk size.
    """

    # --- 1. Clean text ---
    cleaned = " ".join(text.split())  # normalize whitespace

    # --- 2. Split into sentences ---
    sents = sentence_split(cleaned)

    chunks = []
    current_sents = []
    current_tokens = 0

    def count_tokens(s):
        return len(tokenizer.encode(s))

    def flush_chunk(chunk_id, sents_list):
        if not sents_list:
            return None
        chunk_text = " ".join(sents_list)
        chunk_text = " ".join(chunk_text.split())  # normalize again
        return {"chunk_id": chunk_id, "text": chunk_text}

    chunk_id = 0

    for sent in sents:
        sent_tokens = count_tokens(sent)

        # If adding this sentence fits within max_tokens
        if current_tokens + sent_tokens <= max_tokens:
            current_sents.append(sent)
            current_tokens += sent_tokens
            continue

        # Otherwise: flush current chunk if it's big enough
        if current_tokens >= min_chunk_tokens:
            chunk = flush_chunk(chunk_id, current_sents)
            if chunk:
                chunks.append(chunk)
                chunk_id += 1
        else:
            # If too small, try to add anyway (avoid tiny chunks)
            current_sents.append(sent)
            current_tokens += sent_tokens
            continue

        # --- 3. Build token-based overlap ---
        if overlap > 0:
            overlap_sents = []
            overlap_tokens = 0

            # Walk backwards through current_sents
            for s in reversed(current_sents):
                t = count_tokens(s)
                if overlap_tokens + t > overlap:
                    break
                overlap_sents.insert(0, s)
                overlap_tokens += t

            current_sents = overlap_sents
            current_tokens = overlap_tokens
        else:
            current_sents = []
            current_tokens = 0

        # Add the new sentence
        current_sents.append(sent)
        current_tokens += sent_tokens

    # --- 4. Flush final chunk ---
    if current_sents:
        chunk = flush_chunk(chunk_id, current_sents)
        if chunk:
            chunks.append(chunk)

    return chunks



if __name__ == "__main__":
    t = Path(__file__).parent.parent / "data" / "raw_docs" / "sample.txt"
    if t.exists():
        text = t.read_text()
        ch = chunk_text(text)
        print("Chunks:", len(ch))