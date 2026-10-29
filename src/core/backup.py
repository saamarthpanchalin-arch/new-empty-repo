import json
import hashlib
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.core.sqlite_store import SQLiteStore
from src.core.qdrant_store import QdrantStore


class BackupService:
    def __init__(self, sqlite_store: SQLiteStore, qdrant_store: QdrantStore):
        self.sqlite = sqlite_store
        self.qdrant = qdrant_store

    def export_backup(self, app_id: str, collection_id: str) -> Dict[str, Any]:
        """Export all data for an application/collection to a backup dict."""
        # Get SQLite data
        app = self.sqlite.get_application(app_id)
        collection = self.sqlite.get_collection(app_id, collection_id)
        documents = self.sqlite.get_documents(app_id, collection_id)
        
        chunks = []
        for doc in documents:
            doc_chunks = self.sqlite.get_chunks_for_document(app_id, collection_id, doc['id'])
            chunks.extend(doc_chunks)
        
        # Get Qdrant vectors
        qdrant_collection = f"{app_id}_{collection_id}"
        vectors = self.qdrant.get_all_points_with_vectors(qdrant_collection, limit=10000)
        
        # Audit log
        self.sqlite.log_audit(app_id, "backup_exported", {
            "collection_id": collection_id,
            "documents": len(documents),
            "chunks": len(chunks),
            "vectors": len(vectors),
        })
        
        return {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "application": app,
            "collection": collection,
            "documents": documents,
            "chunks": chunks,
            "vectors": vectors,
        }

    def import_backup(self, backup_data: Dict[str, Any], new_app_id: str, new_collection_id: str) -> Dict[str, Any]:
        """Import backup data into a new application/collection."""
        # Create new application
        self.sqlite.register_application(
            new_app_id,
            backup_data["application"]["name"],
            backup_data["application"].get("description"),
        )
        
        # Create new collection
        self.sqlite.create_collection(
            app_id=new_app_id,
            collection_id=new_collection_id,
            name=backup_data["collection"]["name"],
            embedding_model=backup_data["collection"]["embedding_model"],
            embedding_dim=backup_data["collection"]["embedding_dim"],
            chunk_strategy=backup_data["collection"]["chunk_strategy"],
            chunk_size=backup_data["collection"]["chunk_size"],
            chunk_overlap=backup_data["collection"]["chunk_overlap"],
            description=backup_data["collection"].get("description"),
        )
        
        # Import documents and chunks - generate new chunk IDs to avoid PRIMARY KEY conflicts

        for doc in backup_data["documents"]:
            new_doc_id = doc["id"]
            self.sqlite.save_document(
                app_id=new_app_id,
                collection_id=new_collection_id,
                doc_id=new_doc_id,
                source_uri=doc["source_uri"],
                source_type=doc["source_type"],
                content_hash=doc["content_hash"],
                metadata=doc.get("metadata", {}),
                access_scope=doc.get("access_scope", "private"),
                version=doc.get("document_version", 1),
            )
        
        # Generate new chunk IDs for restored chunks to avoid PRIMARY KEY conflicts
        # Map old chunk_id -> new chunk_id
        chunk_id_map = {}
        for chunk in backup_data["chunks"]:
            new_chunk_id = str(uuid.uuid4())
            chunk_id_map[chunk["chunk_id"]] = new_chunk_id
        
        for chunk in backup_data["chunks"]:
            self.sqlite.save_chunk(
                chunk_id=chunk_id_map[chunk["chunk_id"]],
                app_id=new_app_id,
                collection_id=new_collection_id,
                doc_id=chunk["document_id"],
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                content_hash=chunk["content_hash"],
                start_offset=chunk.get("start_offset"),
                end_offset=chunk.get("end_offset"),
                metadata=chunk.get("metadata", {}),
            )
        
        # Import Qdrant vectors with new point IDs (based on content hash for stability)
        qdrant_collection = f"{new_app_id}_{new_collection_id}"
        self.qdrant.create_collection(qdrant_collection, vector_size=backup_data["collection"]["embedding_dim"])
        
        points = []
        for vector in backup_data["vectors"]:
            payload = vector.get("payload", {})
            # Update payload with new app/collection IDs and new chunk ID
            payload["application_id"] = new_app_id
            payload["collection_id"] = new_collection_id
            
            # Use old chunk_id to map to new chunk_id
            old_chunk_id = payload.get("chunk_id")
            if old_chunk_id and old_chunk_id in chunk_id_map:
                payload["chunk_id"] = chunk_id_map[old_chunk_id]
            
            # Use stable point ID based on content hash
            content = payload.get("content", "")
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            # Convert first 32 chars of hash to valid UUID
            point_id = str(uuid.UUID(content_hash[:32]))
            
            points.append({
                "id": point_id,
                "vector": vector.get("vector", []),
                "payload": payload,
            })
        
        if points:
            self.qdrant.upsert_points(qdrant_collection, points)
        
        # Audit log
        self.sqlite.log_audit(new_app_id, "backup_imported", {
            "collection_id": new_collection_id,
            "documents": len(backup_data["documents"]),
            "chunks": len(backup_data["chunks"]),
            "vectors": len(points),
        })
        
        return {
            "documents": len(backup_data["documents"]),
            "chunks": len(backup_data["chunks"]),
            "vectors": len(points),
        }
