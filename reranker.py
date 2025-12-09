"""
Reranker Module using LLM-based reranking
For Travel Business RAG System
"""
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from openai import OpenAI


@dataclass
class RankedResult:
    """A reranked search result"""
    content: str
    metadata: Dict[str, Any]
    original_score: float
    rerank_score: float
    relevance_explanation: Optional[str] = None


class LLMReranker:
    """
    Reranker using LLM (GPT-4) for intelligent relevance scoring.
    Best for complex queries where semantic understanding matters.
    """

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=openai_api_key)
        self.model = model

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[RankedResult]:
        """
        Rerank results using LLM scoring.
        Scores each result for relevance to the query.
        """
        if not results:
            return []

        ranked_results = []

        for result in results:
            content = result.get('content', '')[:1500]
            score, explanation = self._score_relevance(query, content)

            ranked_results.append(RankedResult(
                content=result.get('content', ''),
                metadata=result.get('metadata', {}),
                original_score=result.get('score', 0),
                rerank_score=score,
                relevance_explanation=explanation
            ))

        ranked_results.sort(key=lambda x: x.rerank_score, reverse=True)
        return ranked_results[:top_k]

    def _score_relevance(self, query: str, content: str) -> tuple:
        """Score content relevance to query using LLM"""
        prompt = f"""Score the relevance of this travel information to the query on a scale of 0-10.

Query: {query}

Information:
{content}

Respond with ONLY a JSON object:
{{"score": <number 0-10>, "reason": "<brief explanation>"}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=100
            )

            import json
            result = json.loads(response.choices[0].message.content)
            return float(result.get('score', 5)) / 10.0, result.get('reason', '')

        except Exception as e:
            print(f"LLM scoring error: {e}")
            return 0.5, "Error scoring"

    def batch_rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[RankedResult]:
        """
        Batch rerank using a single LLM call for efficiency.
        """
        if not results:
            return []

        # Format documents for batch scoring
        docs_text = ""
        for i, result in enumerate(results):
            content = result.get('content', '')[:500]
            docs_text += f"\n[Doc {i+1}]: {content}\n"

        prompt = f"""Score each document's relevance to the travel query (0-10).

Query: {query}

Documents:{docs_text}

Respond with ONLY a JSON array of scores:
[{{"doc": 1, "score": <0-10>}}, {{"doc": 2, "score": <0-10>}}, ...]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500
            )

            import json
            scores_data = json.loads(response.choices[0].message.content)
            scores_map = {s['doc']: s['score'] for s in scores_data}

            ranked_results = []
            for i, result in enumerate(results):
                score = scores_map.get(i + 1, 5) / 10.0
                ranked_results.append(RankedResult(
                    content=result.get('content', ''),
                    metadata=result.get('metadata', {}),
                    original_score=result.get('score', 0),
                    rerank_score=score
                ))

            ranked_results.sort(key=lambda x: x.rerank_score, reverse=True)
            return ranked_results[:top_k]

        except Exception as e:
            print(f"Batch reranking error: {e}")
            return [
                RankedResult(
                    content=r.get('content', ''),
                    metadata=r.get('metadata', {}),
                    original_score=r.get('score', 0),
                    rerank_score=r.get('score', 0)
                )
                for r in results[:top_k]
            ]


class CrossEncoderReranker:
    """
    Reranker using sentence-transformers Cross-Encoder.
    Falls back to passthrough if not available.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.cross_encoder = None
        self._load_model()

    def _load_model(self):
        """Try to load the cross-encoder model"""
        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(self.model_name)
            print(f"Cross-encoder loaded: {self.model_name}")
        except ImportError:
            print("sentence-transformers not installed, using fallback reranking")
        except Exception as e:
            print(f"Failed to load cross-encoder: {e}")

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[RankedResult]:
        """Rerank results using cross-encoder"""
        if not results:
            return []

        if self.cross_encoder is None:
            return [
                RankedResult(
                    content=r.get('content', ''),
                    metadata=r.get('metadata', {}),
                    original_score=r.get('score', 0),
                    rerank_score=r.get('score', 0)
                )
                for r in results[:top_k]
            ]

        pairs = [(query, r.get('content', '')) for r in results]
        scores = self.cross_encoder.predict(pairs)

        ranked_results = []
        for i, (result, score) in enumerate(zip(results, scores)):
            ranked_results.append(RankedResult(
                content=result.get('content', ''),
                metadata=result.get('metadata', {}),
                original_score=result.get('score', 0),
                rerank_score=float(score)
            ))

        ranked_results.sort(key=lambda x: x.rerank_score, reverse=True)
        return ranked_results[:top_k]


def create_reranker(
    openai_api_key: str,
    use_cross_encoder: bool = False,
    use_llm: bool = True
) -> Any:
    """Factory function to create appropriate reranker"""
    if use_llm:
        return LLMReranker(openai_api_key)
    elif use_cross_encoder:
        return CrossEncoderReranker()
    else:
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")

    # Test data
    query = "What should I do on Day 1 of the Rajasthan trip?"
    results = [
        {
            "content": "DAY 1: PUNE TO JAIPUR - Arrival at 08:15 AM. Visit Amber Fort (11:30 AM), Hawa Mahal (04:15 PM), City Palace (05:15 PM). Dinner at hotel.",
            "metadata": {"source": "itinerary.txt", "section": "day_1"},
            "score": 0.85
        },
        {
            "content": "Amit Sharma - Customer ID CUST001, traveling from 15-Dec to 22-Dec. Currently on Day 3 in Pushkar.",
            "metadata": {"source": "customers.txt", "section": "customer_1"},
            "score": 0.72
        },
        {
            "content": "Hotel Clarks Amer in Jaipur. Address: JLN Marg, Malviya Nagar. Check-in arranged for 09:15 AM.",
            "metadata": {"source": "itinerary.txt", "section": "hotel"},
            "score": 0.68
        }
    ]

    print("=== Testing Rerankers ===\n")

    if api_key:
        print("LLM Reranker:")
        llm_reranker = LLMReranker(api_key)
        llm_results = llm_reranker.batch_rerank(query, results, top_k=3)
        for r in llm_results:
            print(f"  [{r.rerank_score:.3f}] {r.metadata.get('section')}")
            print(f"    {r.content[:80]}...")
