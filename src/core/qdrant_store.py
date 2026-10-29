from typing import List, Dict, Any, Optional
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid

logger = logging.getLogger(__name__)

class QdrantStore:
    def __init__(self, host: str = "localhost", port: int = 6333, use_memory: bool = False):
        """
        Initialize Qdrant client.
        use_memory: If True, use in-memory mode for testing (no persistence).
        """
        self.use_memory = use_memory
        if use_memory:
            self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(host=host, port=port)

    def create_collection(self, collection_name: str, vector_size: int = 384, distance: str = "Cosine") -> bool:
        """Create a new collection if it doesn't exist."""
        try:
            self.client.get_collection(collection_name)
            logger.info(f"Collection {collection_name} already exists")
        except Exception:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=distance),
            )
            # Create payload index for filtering
            for field in ["application_id", "collection_id", "document_id", "chunk_index"]:
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass  # Index might already exist
            logger.info(f"Created collection {collection_name}")
        return True

    def upsert_points(
        self,
        collection_name: str,
        points: List[Dict[str, Any]],
    ) -> bool:
        """Upsert points with vectors and payload."""
        qdrant_points = []
        for p in points:
            qdrant_points.append(models.PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {})
            ))
        self.client.upsert(collection_name=collection_name, points=qdrant_points)
        return True

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        filter_conditions: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        query_filter = None
        if filter_conditions:
            must_conditions = []
            for key, value in filter_conditions.items():
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )
            query_filter = models.Filter(must=must_conditions)

        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )
        
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload,
                "vector": hit.vector if with_vectors else None,
            }
            for hit in results.points
        ]

    def delete_points(self, collection_name: str, point_ids: List[str]) -> bool:
        """Delete points by ID."""
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=point_ids),
        )
        return True

    def delete_by_filter(self, collection_name: str, filter_conditions: Dict[str, Any]) -> bool:
        """Delete points matching filter."""
        must_conditions = [
            models.FieldCondition(key=k, match=models.MatchValue(value=v))
            for k, v in filter_conditions.items()
        ]
        query_filter = models.Filter(must=must_conditions)
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(filter=query_filter),
        )
        return True

    def scroll(
        self,
        collection_name: str,
        filter_conditions: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Scroll through points with optional filtering."""
        query_filter = None
        if filter_conditions:
            must_conditions = [
                models.FieldCondition(key=k, match=models.MatchValue(value=v))
                for k, v in filter_conditions.items()
            ]
            query_filter = models.Filter(must=must_conditions)
        
        points, _ = self.client.scroll(
            collection_name=collection_name,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [{"id": p.id, "payload": p.payload} for p in points]

    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get collection statistics."""
        try:
            info = self.client.get_collection(collection_name)
            return {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception:
            return None

    def get_all_points_with_vectors(self, collection_name: str, limit: int = 10000) -> List[Dict[str, Any]]:
        """Get all points with vectors from a collection (for backup)."""
        points, _ = self.client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )
        return [
            {
                "id": p.id,
                "vector": p.vector,
                "payload": p.payload,
            }
            for p in points
        ]