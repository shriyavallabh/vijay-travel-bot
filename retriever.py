"""
Hybrid Retriever: BM25 + Vector Search with Reciprocal Rank Fusion
For Travel Business RAG System
"""
import os
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from rank_bm25 import BM25Okapi
from openai import OpenAI
import tiktoken


@dataclass
class Document:
    """A document chunk with metadata"""
    id: str
    content: str
    metadata: Dict[str, Any]
    source: str


@dataclass
class SearchResult:
    """A search result with score"""
    document: Document
    score: float
    source: str  # 'bm25', 'vector', or 'hybrid'


class HybridRetriever:
    """
    Combines BM25 (lexical) and Vector (semantic) search
    using Reciprocal Rank Fusion (RRF) for final ranking.
    """

    def __init__(self, openai_api_key: str, embedding_model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Storage
        self.documents: List[Document] = []
        self.embeddings: np.ndarray = None
        self.bm25: BM25Okapi = None

        # BM25 tokenized corpus
        self._tokenized_corpus: List[List[str]] = []

    def add_documents(self, documents: List[Document]):
        """Add documents to the retriever"""
        self.documents.extend(documents)
        self._rebuild_indices()

    def add_document(self, doc: Document):
        """Add a single document"""
        self.documents.append(doc)
        self._rebuild_indices()

    def _rebuild_indices(self):
        """Rebuild both BM25 and vector indices"""
        if not self.documents:
            return

        # Build BM25 index
        self._tokenized_corpus = [
            self._tokenize(doc.content) for doc in self.documents
        ]
        self.bm25 = BM25Okapi(self._tokenized_corpus)

        # Build vector index
        texts = [doc.content for doc in self.documents]
        self.embeddings = self._get_embeddings_batch(texts)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25"""
        text = text.lower()
        tokens = []
        current_token = ""
        for char in text:
            if char.isalnum():
                current_token += char
            else:
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
        if current_token:
            tokens.append(current_token)
        return tokens

    def _get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for multiple texts"""
        if not texts:
            return np.array([])

        # Batch API call
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts
        )

        embeddings = [item.embedding for item in response.data]
        return np.array(embeddings)

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for single text"""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=[text]
        )
        return np.array(response.data[0].embedding)

    def search_bm25(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Lexical search using BM25"""
        if not self.bm25:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append(SearchResult(
                    document=self.documents[idx],
                    score=float(scores[idx]),
                    source='bm25'
                ))

        return results

    def search_vector(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Semantic search using vector similarity"""
        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        query_embedding = self._get_embedding(query)

        # Cosine similarity
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append(SearchResult(
                document=self.documents[idx],
                score=float(similarities[idx]),
                source='vector'
            ))

        return results

    def search_hybrid(
        self,
        query: str,
        top_k: int = 10,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        use_rrf: bool = True
    ) -> List[SearchResult]:
        """
        Hybrid search combining BM25 and Vector results.
        """
        # Get results from both methods
        bm25_results = self.search_bm25(query, top_k * 2)
        vector_results = self.search_vector(query, top_k * 2)

        if use_rrf:
            return self._reciprocal_rank_fusion(bm25_results, vector_results, top_k)
        else:
            return self._weighted_fusion(
                bm25_results, vector_results,
                bm25_weight, vector_weight, top_k
            )

    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[SearchResult],
        vector_results: List[SearchResult],
        top_k: int,
        k: int = 60
    ) -> List[SearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.
        RRF score = sum(1 / (k + rank)) for each ranking list
        """
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        # Score from BM25 ranking
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result.document.id
            rrf_score = 1.0 / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score
            doc_map[doc_id] = result.document

        # Score from Vector ranking
        for rank, result in enumerate(vector_results, 1):
            doc_id = result.document.id
            rrf_score = 1.0 / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score
            doc_map[doc_id] = result.document

        # Sort by RRF score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for doc_id, score in sorted_docs[:top_k]:
            results.append(SearchResult(
                document=doc_map[doc_id],
                score=score,
                source='hybrid'
            ))

        return results

    def _weighted_fusion(
        self,
        bm25_results: List[SearchResult],
        vector_results: List[SearchResult],
        bm25_weight: float,
        vector_weight: float,
        top_k: int
    ) -> List[SearchResult]:
        """Combine results using weighted score fusion"""
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        # Normalize BM25 scores
        if bm25_results:
            max_bm25 = max(r.score for r in bm25_results)
            for result in bm25_results:
                doc_id = result.document.id
                normalized_score = result.score / max_bm25 if max_bm25 > 0 else 0
                doc_scores[doc_id] = doc_scores.get(doc_id, 0) + bm25_weight * normalized_score
                doc_map[doc_id] = result.document

        # Vector scores are already normalized
        for result in vector_results:
            doc_id = result.document.id
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + vector_weight * result.score
            doc_map[doc_id] = result.document

        # Sort by combined score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for doc_id, score in sorted_docs[:top_k]:
            results.append(SearchResult(
                document=doc_map[doc_id],
                score=score,
                source='hybrid'
            ))

        return results

    def stats(self) -> Dict[str, Any]:
        """Get retriever statistics"""
        return {
            "num_documents": len(self.documents),
            "embedding_dim": self.embeddings.shape[1] if self.embeddings is not None and len(self.embeddings) > 0 else 0,
            "bm25_initialized": self.bm25 is not None
        }


class DocumentChunker:
    """
    Chunks documents for better retrieval.
    Uses semantic chunking with overlap.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk_text(self, text: str, doc_id: str, metadata: Dict[str, Any]) -> List[Document]:
        """Split text into overlapping chunks"""
        tokens = self.tokenizer.encode(text)

        if len(tokens) <= self.chunk_size:
            return [Document(
                id=f"{doc_id}_0",
                content=text,
                metadata={**metadata, "chunk_index": 0},
                source=metadata.get("source", "unknown")
            )]

        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)

            chunks.append(Document(
                id=f"{doc_id}_{chunk_idx}",
                content=chunk_text,
                metadata={**metadata, "chunk_index": chunk_idx},
                source=metadata.get("source", "unknown")
            ))

            start = end - self.chunk_overlap
            chunk_idx += 1

        return chunks

    def chunk_text_file(self, file_path: str) -> List[Document]:
        """Chunk a text file with smart section handling"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        from pathlib import Path
        filename = Path(file_path).stem

        metadata = {
            "source": file_path,
            "filename": filename,
            "type": "travel_data"
        }

        # Split by major sections
        sections = self._split_by_sections(content)

        documents = []
        for section_name, section_content in sections:
            section_meta = {**metadata, "section": section_name}

            # Chunk each section
            section_chunks = self.chunk_text(
                section_content,
                f"{filename}_{section_name}",
                section_meta
            )
            documents.extend(section_chunks)

        return documents

    def _split_by_sections(self, content: str) -> List[Tuple[str, str]]:
        """Split text by major section markers (=== or ---)"""
        import re

        sections = []
        current_section = "header"
        current_content = []

        # Split by lines
        for line in content.split('\n'):
            # Check for section headers (=== lines followed by section name)
            if line.strip().startswith('===') or (line.strip().startswith('DAY') and ':' in line):
                # Save previous section
                if current_content:
                    sections.append((current_section, '\n'.join(current_content)))

                # Extract new section name
                if 'DAY' in line:
                    current_section = line.strip().split(':')[0].lower().replace(' ', '_')
                elif len(current_content) > 0:
                    # Use the line before === as section name
                    current_section = current_content[-1].strip().lower().replace(' ', '_')[:50]
                current_content = [line]
            elif line.strip().startswith('CUSTOMER') and ':' in line:
                # Save previous section
                if current_content:
                    sections.append((current_section, '\n'.join(current_content)))
                current_section = f"customer_{line.split(':')[0].split()[-1]}"
                current_content = [line]
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections.append((current_section, '\n'.join(current_content)))

        return sections


def create_retriever_from_directory(
    directory: str,
    openai_api_key: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100
) -> HybridRetriever:
    """
    Create a retriever from a directory of text files.
    """
    retriever = HybridRetriever(openai_api_key)
    chunker = DocumentChunker(chunk_size, chunk_overlap)

    all_documents = []

    for filename in os.listdir(directory):
        if filename.endswith('.txt'):
            file_path = os.path.join(directory, filename)
            try:
                chunks = chunker.chunk_text_file(file_path)
                all_documents.extend(chunks)
                print(f"  Chunked: {filename} -> {len(chunks)} chunks")
            except Exception as e:
                print(f"  Error chunking {filename}: {e}")

    if all_documents:
        print(f"\nBuilding indices for {len(all_documents)} documents...")
        retriever.add_documents(all_documents)
        print(f"Retriever ready: {retriever.stats()}")

    return retriever


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("OPENAI_API_KEY not set")
        sys.exit(1)

    print("Creating hybrid retriever...")
    retriever = create_retriever_from_directory(data_dir, api_key)

    # Test queries
    test_queries = [
        "What is on Day 1 of the trip?",
        "Amber Fort visit timing",
        "Amit Sharma booking details",
        "What hotels are in Udaipur?"
    ]

    for query in test_queries:
        print(f"\n=== Query: {query} ===")

        # Hybrid search
        hybrid_results = retriever.search_hybrid(query, top_k=3)
        print(f"\nHybrid Results (RRF):")
        for r in hybrid_results:
            print(f"  [{r.score:.4f}] {r.document.metadata.get('section', 'unknown')}")
            print(f"    {r.document.content[:150]}...")
