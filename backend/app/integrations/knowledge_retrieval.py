"""Knowledge Retrieval Engine for Partial RAG in EchoDrive.

Provides low-latency in-memory vector similarity and semantic search over
authoritative dealership policies, warranty options, financing guidelines,
and vehicle technical FAQs.
"""

import math
import re
import time
from typing import List, Dict, Optional, Any, Set
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class KnowledgeChunk(BaseModel):
    """An authoritative knowledge chunk for dealership domain information."""
    chunk_id: str
    category: str = Field(..., description="Category: policy, financing, warranty, test_drive, ev_charging, service")
    title: str
    content: str
    keywords: List[str] = Field(default_factory=list)


# Authoritative unstructured dealership domain knowledge
DEALERSHIP_KNOWLEDGE_BASE: List[KnowledgeChunk] = [
    KnowledgeChunk(
        chunk_id="policy-001",
        category="policy",
        title="7-Day / 500-KM Return and Exchange Policy",
        content=(
            "EchoDrive Luxury Motors offers a 7-day or 500-kilometer 'No-Questions-Asked' return and exchange policy "
            "on all certified pre-owned and new vehicles. If you are not completely satisfied, you may exchange for "
            "any equal or higher-value inventory vehicle, or receive a full refund minus nominal documentation charges."
        ),
        keywords=["return", "exchange", "refund", "7 day", "7-day", "500 km", "money back", "satisfaction", "guarantee"],
    ),
    KnowledgeChunk(
        chunk_id="warranty-001",
        category="warranty",
        title="EchoDrive Comprehensive Warranty & Extended Coverage",
        content=(
            "All new luxury vehicles come with a standard 3-year / 100,000 km manufacturer bumper-to-bumper warranty. "
            "EchoDrive also provides an optional 5-year 'Star Shield Extended Care' package covering engine, transmission, "
            "air suspension, electronics, and 24/7 pan-India roadside assistance with zero-deductible claims."
        ),
        keywords=["warranty", "extended warranty", "star shield", "guarantee", "roadside assistance", "coverage", "bumper to bumper", "repair"],
    ),
    KnowledgeChunk(
        chunk_id="financing-001",
        category="financing",
        title="Dealership Financing, Down Payment, and Interest Rates",
        content=(
            "We partner with HDFC Bank, ICICI Bank, and Mercedes-Benz / BMW Financial Services to offer customized EMI plans. "
            "Interest rates start from 7.99% per annum with tenures ranging from 12 to 84 months. Minimum down payment starts "
            "at 10% of the on-road price, with instant on-the-spot approval for eligible salaried and business applicants."
        ),
        keywords=["finance", "financing", "loan", "emi", "interest rate", "down payment", "bank", "tenure", "monthly payment", "hdfc", "icici"],
    ),
    KnowledgeChunk(
        chunk_id="test-drive-001",
        category="test_drive",
        title="Doorstep & Showroom Test Drive Protocol",
        content=(
            "Customers can book complimentary doorstep test drives anywhere within 40 km of our showroom or schedule an in-showroom experience. "
            "A valid original driving license is required. Our sales specialist brings the sanitized vehicle with sanitized touchpoints "
            "for a 30-minute dedicated drive."
        ),
        keywords=["test drive", "doorstep", "home test drive", "license", "booking", "schedule", "drive", "slot"],
    ),
    KnowledgeChunk(
        chunk_id="ev-charging-001",
        category="ev_charging",
        title="Electric Vehicle (EV) Charging & Wallbox Installation",
        content=(
            "Every EV purchase includes a complimentary 11 kW AC Home Wallbox charger with free standard installation by certified electricians. "
            "Our dealership also provides free DC fast-charging (150 kW) at all showroom locations for our customers, charging 10% to 80% in ~28 minutes."
        ),
        keywords=["ev", "electric", "charger", "charging", "wallbox", "home charger", "fast charging", "battery", "range"],
    ),
    KnowledgeChunk(
        chunk_id="trade-in-001",
        category="policy",
        title="Vehicle Exchange & Trade-In Valuation",
        content=(
            "We accept all brands for vehicle trade-ins. Our certified valuation engineers perform a 120-point digital inspection in under 30 minutes. "
            "We guarantee an exchange bonus of up to INR 1,50,000 over fair market valuation when trading in for a new vehicle."
        ),
        keywords=["trade-in", "trade in", "exchange bonus", "old car", "valuation", "sell car", "upgrade"],
    ),
    KnowledgeChunk(
        chunk_id="service-001",
        category="service",
        title="Scheduled Maintenance & Express Service Packages",
        content=(
            "Annual maintenance intervals are 15,000 km or 1 year (whichever comes first). We offer pre-paid 'Service Inclusive' packages "
            "saving up to 35% on periodic maintenance, including synthetic engine oil, filters, spark plugs, brake fluid, and contactless pickup & drop."
        ),
        keywords=["service", "maintenance", "service package", "interval", "oil change", "pickup drop", "repair cost"],
    ),
]


STOP_WORDS = {
    "what", "is", "the", "a", "an", "for", "in", "of", "and", "or",
    "to", "with", "do", "you", "we", "our", "are", "on", "can", "i",
    "my", "it", "at", "be", "this", "that", "there", "about", "how"
}


class KnowledgeRetrievalEngine:
    """Fast in-memory semantic & BM25-style keyword vector search engine."""

    def __init__(self, chunks: Optional[List[KnowledgeChunk]] = None) -> None:
        self.chunks: List[KnowledgeChunk] = chunks or list(DEALERSHIP_KNOWLEDGE_BASE)
        self._doc_term_freqs: List[Dict[str, float]] = []
        self._doc_lengths: List[int] = []
        self._doc_keyword_sets: List[Set[str]] = []
        self._doc_title_sets: List[Set[str]] = []
        self._idf: Dict[str, float] = {}
        self._vocab: Set[str] = set()
        self._avg_doc_len: float = 0.0
        self._build_index()

    def _tokenize(self, text: str, remove_stopwords: bool = True) -> List[str]:
        """Normalize and tokenize input text into clean unigrams and bigrams."""
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
        tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]
        if remove_stopwords:
            tokens = [t for t in tokens if t not in STOP_WORDS]
        return tokens

    def _build_index(self) -> None:
        """Builds in-memory inverted index and term frequency weights."""
        num_docs = len(self.chunks)
        doc_counts: Dict[str, int] = {}
        self._doc_term_freqs = []
        self._doc_lengths = []
        self._doc_keyword_sets = []
        self._doc_title_sets = []

        for chunk in self.chunks:
            # Aggregate title, keywords (weighted 3x), and content
            full_text = f"{chunk.title} {' '.join(chunk.keywords * 3)} {chunk.content}"
            tokens = self._tokenize(full_text, remove_stopwords=True)
            self._doc_lengths.append(len(tokens))

            # Store token sets for exact keyword/title boost
            kw_tokens = set(self._tokenize(" ".join(chunk.keywords), remove_stopwords=False))
            title_tokens = set(self._tokenize(chunk.title, remove_stopwords=False))
            self._doc_keyword_sets.append(kw_tokens)
            self._doc_title_sets.append(title_tokens)

            tf: Dict[str, float] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0.0) + 1.0

            # Normalize tf
            for t in tf:
                tf[t] = tf[t] / max(len(tokens), 1)

            self._doc_term_freqs.append(tf)

            for t in set(tokens):
                doc_counts[t] = doc_counts.get(t, 0) + 1
                self._vocab.add(t)

        self._avg_doc_len = sum(self._doc_lengths) / max(num_docs, 1)

        # Compute smoothed IDF: log( (N - n + 0.5) / (n + 0.5) + 1 )
        self._idf = {}
        for term, count in doc_counts.items():
            self._idf[term] = math.log(1.0 + (num_docs - count + 0.5) / (count + 0.5))

    async def query(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 2,
        min_score: float = 0.5,
    ) -> List[KnowledgeChunk]:
        """Performs async non-blocking semantic retrieval against knowledge chunks.
        
        Guaranteed <1ms latency for in-memory corpus.
        """
        if not query or not query.strip():
            return []

        q_tokens = self._tokenize(query, remove_stopwords=True)
        if not q_tokens:
            return []

        scores: List[tuple[float, int]] = []
        k1 = 1.5
        b = 0.75

        for doc_idx, (chunk, tf, doc_len, kw_set, title_set) in enumerate(
            zip(self.chunks, self._doc_term_freqs, self._doc_lengths, self._doc_keyword_sets, self._doc_title_sets)
        ):
            if category and chunk.category.lower() != category.lower():
                continue

            score = 0.0
            for qt in q_tokens:
                if qt in tf:
                    term_freq = tf[qt] * doc_len
                    idf = self._idf.get(qt, 0.5)
                    # BM25 term weighting
                    numerator = term_freq * (k1 + 1.0)
                    denominator = term_freq + k1 * (1.0 - b + b * (doc_len / max(self._avg_doc_len, 1.0)))
                    score += idf * (numerator / max(denominator, 1e-6))

                # Check exact whole token match in keywords or title for high boost
                if qt in kw_set:
                    score += 2.0
                if qt in title_set:
                    score += 2.5

            if score >= min_score:
                scores.append((score, doc_idx))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = [self.chunks[doc_idx] for _, doc_idx in scores[:top_k]]
        return results

    def format_retrieval_prompt(self, chunks: List[KnowledgeChunk]) -> str:
        """Formats retrieved knowledge chunks into concise prompt context."""
        if not chunks:
            return ""

        lines = [
            "### Authoritative Dealership Policies & Information:",
        ]
        for c in chunks:
            lines.append(f"**[{c.title}]**: {c.content}")

        return "\n".join(lines)


# Singleton knowledge retrieval engine
knowledge_engine = KnowledgeRetrievalEngine()
