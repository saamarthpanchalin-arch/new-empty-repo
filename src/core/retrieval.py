import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    content: str
    score: float
    rank: int
    retrieval_method: str  # "vector", "lexical", "hybrid"
    payload: Dict[str, Any]
    source_uri: str
    chunk_index: int

class HybridRetrievalService:
    def __init__(
        self,
        sqlite_store,
        qdrant_store,
        embedding_provider,
    ):
        self.sqlite = sqlite_store
        self.qdrant = qdrant_store
        self.embeddings = embedding_provider

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievalResult],
        lexical_results: List[RetrievalResult],
        k: int = 60,
    ) -> List[RetrievalResult]:
        """Combine results using Reciprocal Rank Fusion."""
        scores = defaultdict(float)
        doc_map = {}

        # Score vector results
        for rank, result in enumerate(vector_results):
            scores[result.chunk_id] += 1.0 / (k + rank + 1)
            doc_map[result.chunk_id] = result

        # Score lexical results
        for rank, result in enumerate(lexical_results):
            scores[result.chunk_id] += 1.0 / (k + rank + 1)
            if result.chunk_id not in doc_map:
                doc_map[result.chunk_id] = result

        # Sort by combined score
        sorted_results = sorted(
            [(chunk_id, doc_map[chunk_id]) for chunk_id in scores],
            key=lambda x: scores[x[0]],
            reverse=True
        )

        # Update scores and methods
        final_results = []
        for rank, (chunk_id, result) in enumerate(sorted_results):
            result = RetrievalResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                content=result.content,
                score=scores[chunk_id],
                rank=rank,
                retrieval_method="hybrid",
                payload=result.payload,
                source_uri=result.source_uri,
                chunk_index=result.chunk_index,
            )
            final_results.append(result)

        return final_results

    def search(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 10,
        filter_conditions: Optional[Dict[str, Any]] = None,
        use_hybrid: bool = True,
        rrf_k: int = 60,
    ) -> List[RetrievalResult]:
        """Search using hybrid retrieval (vector + lexical)."""
        qdrant_collection = f"{app_id}_{collection_id}"
        filter_cond = filter_conditions or {}
        filter_cond["application_id"] = app_id
        filter_cond["collection_id"] = collection_id

        # Vector search
        query_vector = self.embeddings.encode_single(query)
        vector_hits = self.qdrant.search(
            collection_name=qdrant_collection,
            query_vector=query_vector,
            filter_conditions=filter_cond,
            top_k=top_k * 2 if use_hybrid else top_k,  # Get more for fusion
        )

        vector_results = []
        for hit in vector_hits:
            payload = hit.get("payload", {})
            vector_results.append(RetrievalResult(
                chunk_id=hit["id"],
                document_id=payload.get("document_id", ""),
                content=payload.get("content", ""),
                score=hit["score"],
                rank=0,
                retrieval_method="vector",
                payload=payload,
                source_uri=payload.get("source_uri", ""),
                chunk_index=payload.get("chunk_index", 0),
            ))

        # Lexical search
        lexical_hits = self.sqlite.search_lexical(app_id, collection_id, query, top_k * 2 if use_hybrid else top_k)
        
        lexical_results = []
        for hit in lexical_hits:
            lexical_results.append(RetrievalResult(
                chunk_id=hit["chunk_id"],
                document_id=hit["document_id"],
                content=hit["content"],
                score=1.0 / (hit.get("rank", 0) + 1),  # Normalize FTS rank
                rank=0,
                retrieval_method="lexical",
                payload=hit.get("metadata", {}),
                source_uri=hit.get("metadata", {}).get("source_uri", ""),
                chunk_index=hit["chunk_index"],
            ))

        if use_hybrid:
            # Combine with RRF
            combined = self._reciprocal_rank_fusion(vector_results, lexical_results, k=rrf_k)
            return combined[:top_k]
        else:
            # Return only vector results
            for i, r in enumerate(vector_results):
                r.rank = i
            return vector_results[:top_k]

    def search_vector_only(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 10,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """Pure vector similarity search."""
        return self.search(app_id, collection_id, query, top_k, filter_conditions, use_hybrid=False)

    def search_lexical_only(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[RetrievalResult]:
        """Pure lexical (BM25/FTS) search."""
        lexical_hits = self.sqlite.search_lexical(app_id, collection_id, query, top_k)
        results = []
        for hit in lexical_hits:
            results.append(RetrievalResult(
                chunk_id=hit["chunk_id"],
                document_id=hit["document_id"],
                content=hit["content"],
                score=1.0 / (hit.get("rank", 0) + 1),
                rank=len(results),
                retrieval_method="lexical",
                payload=hit.get("metadata", {}),
                source_uri=hit.get("metadata", {}).get("source_uri", ""),
                chunk_index=hit["chunk_index"],
            ))
        return results

    def get_context(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[RetrievalResult]]:
        """Get formatted context string and source results for grounded generation."""
        results = self.search(app_id, collection_id, query, top_k, filter_conditions)
        
        context_parts = []
        for i, result in enumerate(results):
            context_parts.append(
                f"[Source {i+1}]\n"
                f"Document: {result.document_id}\n"
                f"Source: {result.source_uri}\n"
                f"Content: {result.content[:800]}\n"
            )
        
        context = "\n---\n".join(context_parts)
        return context, results