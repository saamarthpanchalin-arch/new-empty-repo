import hashlib
import uuid
import logging
from typing import List, Dict, Any, Optional, Generator
from pathlib import Path
from dataclasses import dataclass

from src.core.sqlite_store import SQLiteStore
from src.core.qdrant_store import QdrantStore
from src.core.embedding import EmbeddingProvider, EmbeddingRegistry
from src.core.parsers import ParserRegistry, ChunkerRegistry, ParsedDocument, Chunker

logger = logging.getLogger(__name__)

@dataclass
class IngestionResult:
    success: bool
    document_id: str
    chunks_created: int
    message: str
    content_hash: str

class IngestionService:
    def __init__(
        self,
        sqlite_store: SQLiteStore,
        qdrant_store: QdrantStore,
        embedding_provider: EmbeddingProvider,
        default_chunk_size: int = 500,
        default_chunk_overlap: int = 50,
        default_chunk_strategy: str = "recursive",
    ):
        self.sqlite = sqlite_store
        self.qdrant = qdrant_store
        self.embeddings = embedding_provider
        self.parser_registry = ParserRegistry()
        self.chunker_registry = ChunkerRegistry()
        self.default_chunk_size = default_chunk_size
        self.default_chunk_overlap = default_chunk_overlap
        self.default_chunk_strategy = default_chunk_strategy

    def ingest_file(
        self,
        app_id: str,
        collection_id: str,
        file_path: str,
        source_uri: Optional[str] = None,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest a single file."""
        path = Path(file_path)
        if not path.exists():
            return IngestionResult(False, "", 0, f"File not found: {file_path}", "")

        # Parse document
        try:
            parsed = self.parser_registry.parse(file_path, source_uri or f"file://{file_path}")
        except Exception as e:
            return IngestionResult(False, "", 0, f"Parse failed: {e}", "")

        # Calculate content hash
        content_hash = hashlib.sha256(parsed.content.encode()).hexdigest()[:32]

        # Check if document already exists with same hash
        if not document_id:
            document_id = str(uuid.uuid4())[:16]

        existing = self.sqlite.get_document(app_id, collection_id, document_id)
        if existing and existing['content_hash'] == content_hash:
            return IngestionResult(True, document_id, 0, "Document unchanged, skipped", content_hash)

        # Get collection config for chunking and validate embedding dimension
        collection = self.sqlite.get_collection(app_id, collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found for application {app_id}")
        
        # Validate embedding dimension matches collection config
        expected_dim = collection.get('embedding_dim')
        actual_dim = self.embeddings.dimension
        if expected_dim and expected_dim != actual_dim:
            raise ValueError(
                f"Embedding dimension mismatch: collection '{collection_id}' expects {expected_dim}-dim vectors, "
                f"but embedding provider produces {actual_dim}-dim vectors. "
                f"Use a matching embedding model or update the collection configuration."
            )
        
        chunk_size = collection.get('chunk_size', self.default_chunk_size)
        chunk_overlap = collection.get('chunk_overlap', self.default_chunk_overlap)
        chunk_strategy = collection.get('chunk_strategy', self.default_chunk_strategy)

        # Chunk document
        chunker = self.chunker_registry.get_chunker(chunk_strategy, chunk_size, chunk_overlap)
        chunks = chunker.chunk(parsed.content, metadata or {})

        # Save document metadata
        self.sqlite.save_document(
            app_id=app_id,
            collection_id=collection_id,
            doc_id=document_id,
            source_uri=source_uri or f"file://{file_path}",
            source_type=parsed.source_type,
            content_hash=content_hash,
            metadata=metadata or {},
        )

        # Delete old chunks if updating
        self.sqlite.delete_document_chunks(app_id, collection_id, document_id)

        # Get Qdrant collection name
        qdrant_collection = f"{app_id}_{collection_id}"
        self.qdrant.create_collection(qdrant_collection, vector_size=self.embeddings.dimension)

        # Embed and upsert chunks
        points = []
        for i, chunk_data in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_content = chunk_data["content"]
            chunk_hash = hashlib.sha256(chunk_content.encode()).hexdigest()[:16]

            # Generate embedding
            embedding = self.embeddings.encode_single(chunk_content)

            # Prepare Qdrant point
            points.append({
                "id": chunk_id,
                "vector": embedding,
                "payload": {
                    "application_id": app_id,
                    "collection_id": collection_id,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "chunk_index": i,
                    "content": chunk_content,
                    "content_hash": chunk_hash,
                    "start_offset": chunk_data.get("start_offset", 0),
                    "end_offset": chunk_data.get("end_offset", 0),
                    "source_uri": source_uri or f"file://{file_path}",
                    **chunk_data.get("metadata", {}),
                }
            })

            # Save chunk metadata in SQLite
            self.sqlite.save_chunk(
                chunk_id=chunk_id,
                app_id=app_id,
                collection_id=collection_id,
                doc_id=document_id,
                chunk_index=i,
                content=chunk_content,
                content_hash=chunk_hash,
                start_offset=chunk_data.get("start_offset"),
                end_offset=chunk_data.get("end_offset"),
                metadata=chunk_data.get("metadata"),
            )

        # Batch upsert to Qdrant
        if points:
            self.qdrant.upsert_points(qdrant_collection, points)

        return IngestionResult(
            success=True,
            document_id=document_id,
            chunks_created=len(chunks),
            message=f"Successfully ingested {len(chunks)} chunks",
            content_hash=content_hash
        )

    def ingest_text(
        self,
        app_id: str,
        collection_id: str,
        text: str,
        source_uri: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_type: str = "text",
    ) -> IngestionResult:
        """Ingest raw text content."""
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
        
        if not document_id:
            document_id = str(uuid.uuid4())[:16]

        existing = self.sqlite.get_document(app_id, collection_id, document_id)
        if existing and existing['content_hash'] == content_hash:
            return IngestionResult(True, document_id, 0, "Document unchanged, skipped", content_hash)

        collection = self.sqlite.get_collection(app_id, collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found for application {app_id}")
        
        # Validate embedding dimension matches collection config
        expected_dim = collection.get('embedding_dim')
        actual_dim = self.embeddings.dimension
        if expected_dim and expected_dim != actual_dim:
            raise ValueError(
                f"Embedding dimension mismatch: collection '{collection_id}' expects {expected_dim}-dim vectors, "
                f"but embedding provider produces {actual_dim}-dim vectors. "
                f"Use a matching embedding model or update the collection configuration."
            )
        
        chunk_size = collection.get('chunk_size', self.default_chunk_size)
        chunk_overlap = collection.get('chunk_overlap', self.default_chunk_overlap)
        chunk_strategy = collection.get('chunk_strategy', self.default_chunk_strategy)

        chunker = self.chunker_registry.get_chunker(chunk_strategy, chunk_size, chunk_overlap)
        chunks = chunker.chunk(text, metadata or {})

        self.sqlite.save_document(
            app_id=app_id,
            collection_id=collection_id,
            doc_id=document_id,
            source_uri=source_uri,
            source_type=source_type,
            content_hash=content_hash,
            metadata=metadata or {},
        )

        self.sqlite.delete_document_chunks(app_id, collection_id, document_id)

        qdrant_collection = f"{app_id}_{collection_id}"
        self.qdrant.create_collection(qdrant_collection, vector_size=self.embeddings.dimension)

        points = []
        for i, chunk_data in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_content = chunk_data["content"]
            chunk_hash = hashlib.sha256(chunk_content.encode()).hexdigest()[:16]
            embedding = self.embeddings.encode_single(chunk_content)

            points.append({
                "id": chunk_id,
                "vector": embedding,
                "payload": {
                    "application_id": app_id,
                    "collection_id": collection_id,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "chunk_index": i,
                    "content": chunk_content,
                    "content_hash": chunk_hash,
                    "start_offset": chunk_data.get("start_offset", 0),
                    "end_offset": chunk_data.get("end_offset", 0),
                    "source_uri": source_uri,
                    **chunk_data.get("metadata", {}),
                }
            })

            self.sqlite.save_chunk(
                chunk_id=chunk_id,
                app_id=app_id,
                collection_id=collection_id,
                doc_id=document_id,
                chunk_index=i,
                content=chunk_content,
                content_hash=chunk_hash,
                start_offset=chunk_data.get("start_offset"),
                end_offset=chunk_data.get("end_offset"),
                metadata=chunk_data.get("metadata"),
            )

        if points:
            self.qdrant.upsert_points(qdrant_collection, points)

        return IngestionResult(
            success=True,
            document_id=document_id,
            chunks_created=len(chunks),
            message=f"Successfully ingested {len(chunks)} chunks",
            content_hash=content_hash
        )

    def delete_document(self, app_id: str, collection_id: str, document_id: str) -> bool:
        """Delete a document and all its chunks."""
        qdrant_collection = f"{app_id}_{collection_id}"
        # Count Qdrant points before deletion
        qdrant_points = self.qdrant.scroll(qdrant_collection, filter_conditions={"document_id": document_id}, limit=10000)
        qdrant_count = len(qdrant_points)
        
        # Delete from Qdrant
        self.qdrant.delete_by_filter(qdrant_collection, {"document_id": document_id})
        # Delete from SQLite (chunks + document metadata)
        self.sqlite.delete_document(app_id, collection_id, document_id)
        
        # Audit log (SQLite delete_document already logs, but add Qdrant info)
        self.sqlite.log_audit(app_id, "document_delete_completed", {
            "document_id": document_id,
            "collection_id": collection_id,
            "qdrant_points_removed": qdrant_count,
        })
        return True