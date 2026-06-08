import math
import regex
from collections import defaultdict
from typing import List, Dict, Any, Set, Tuple

# Constants for BM25
BM25_K1 = 1.5
BM25_B = 0.75

# Unicode-aware split on non-word characters
TOKENIZE_SPLIT_RE = regex.compile(r'[^\p{L}\p{N}]+', regex.UNICODE)

def tokenize(text: str) -> List[str]:
    """
    Lowercase, split on non-word, drop short tokens.
    Unicode-aware so non-Latin scripts work.
    """
    if not text:
        return []

    # Normalize and lowercase
    text = text.lower() # Python strings are already unicode, lowercasing is fine

    # Split using the regex and filter length >= 2
    tokens = [t for t in TOKENIZE_SPLIT_RE.split(text) if len(t) >= 2]
    return tokens

class BM25Engine:
    def __init__(self):
        self.idf: Dict[str, float] = {}
        self.docs: Dict[str, Dict[str, Any]] = {}
        self.avg_dl: float = 0.0
        self.n_docs: int = 0

    def build_index(self, entries: List[Dict[str, Any]]):
        """
        Build a BM25 index from vault entries.
        Each "document" is the concatenation of entry title, keys, and content.
        """
        self.n_docs = len(entries)
        if self.n_docs == 0:
            self.idf = {}
            self.docs = {}
            self.avg_dl = 0.0
            return

        df: Dict[str, int] = defaultdict(int)
        self.docs = {}
        total_len = 0

        for entry in entries:
            # Construct text from title, keys, and content
            title = entry.get('title', '')
            keys = " ".join(entry.get('keys', []))
            content = entry.get('content', '')

            text = f"{title} {keys} {content}"
            tokens = tokenize(text)

            # Calculate term frequencies for this doc
            tf: Dict[str, int] = defaultdict(int)
            for token in tokens:
                tf[token] += 1

            doc_id = entry['id']
            self.docs[doc_id] = {
                'tf': tf,
                'len': len(tokens),
                'entry': entry
            }
            total_len += len(tokens)

            # Update document frequencies (unique terms in this doc)
            for token in tf.keys():
                df[token] += 1

        self.avg_dl = total_len / self.n_docs

        # Pre-compute IDF tables
        self.idf = {}
        for token, freq in df.items():
            # Standard BM25 IDF formula
            # math.log(1 + (N - df + 0.5) / (df + 0.5))
            val = math.log(1.0 + (self.n_docs - freq + 0.5) / (freq + 0.5))
            # Floor at 0.01 to prevent negative/zero weights for very common terms
            self.idf[token] = max(0.01, val)

    def search(self, query: str, limit: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search the BM25 index and return ranked entries.
        """
        if self.n_docs == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Tally term frequencies in the query
        q_tf: Dict[str, int] = defaultdict(int)
        for token in query_tokens:
            q_tf[token] += 1

        scores: Dict[str, float] = defaultdict(float)

        for q_token, q_freq in q_tf.items():
            if q_token not in self.idf:
                continue

            idf_val = self.idf[q_token]

            # Evaluate against all docs that contain this token
            for doc_id, doc_data in self.docs.items():
                doc_tf = doc_data['tf'].get(q_token, 0)
                if doc_tf == 0:
                    continue

                doc_len = doc_data['len']

                # BM25 term score
                numerator = doc_tf * (BM25_K1 + 1)
                denominator = doc_tf + BM25_K1 * (1 - BM25_B + BM25_B * (doc_len / self.avg_dl))

                # We can ignore query term saturation for short queries or include it:
                # q_weight = (q_freq * (k3 + 1)) / (q_freq + k3) -- simplified to just 1 for boolean queries

                term_score = idf_val * (numerator / denominator)
                scores[doc_id] += term_score

        # Rank and return top results
        ranked = []
        for doc_id, score in scores.items():
            if score > 0:
                ranked.append((self.docs[doc_id]['entry'], score))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:limit]
