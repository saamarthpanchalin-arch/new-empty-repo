from typing import List, Dict, Any, Optional
import requests
import uuid
import os

class LocalRAGClient:
    """Python SDK for Local RAG Knowledge Infrastructure."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
    
    # Health
    def health(self) -> Dict[str, Any]:
        return self.session.get(f"{self.base_url}/health/").json()
    
    def ready(self) -> Dict[str, Any]:
        return self.session.get(f"{self.base_url}/health/ready").json()
    
    # Applications
    def register_application(self, app_id: str, name: str, description: str = "") -> Dict[str, Any]:
        resp = self.session.post(f"{self.base_url}/applications/", json={
            "id": app_id,
            "name": name,
            "description": description,
        })
        resp.raise_for_status()
        return resp.json()
    
    def get_application(self, app_id: str) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/applications/{app_id}")
        resp.raise_for_status()
        return resp.json()
    
    def list_applications(self) -> List[Dict[str, Any]]:
        resp = self.session.get(f"{self.base_url}/applications/")
        resp.raise_for_status()
        return resp.json()
    
    # Collections
    def create_collection(
        self,
        app_id: str,
        collection_id: str,
        name: str,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        chunk_strategy: str = "recursive",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        description: str = "",
    ) -> Dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/applications/{app_id}/collections",
            json={
                "id": collection_id,
                "name": name,
                "embedding_model": embedding_model,
                "chunk_strategy": chunk_strategy,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "description": description,
            }
        )
        resp.raise_for_status()
        return resp.json()
    
    def get_collection(self, app_id: str, collection_id: str) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/applications/{app_id}/collections/{collection_id}")
        resp.raise_for_status()
        return resp.json()
    
    def list_collections(self, app_id: str) -> List[Dict[str, Any]]:
        resp = self.session.get(f"{self.base_url}/applications/{app_id}/collections")
        resp.raise_for_status()
        return resp.json()
    
    # Ingestion
    def ingest_text(
        self,
        app_id: str,
        collection_id: str,
        text: str,
        source_uri: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/ingest/text",
            params={"app_id": app_id, "collection_id": collection_id},
            json={
                "text": text,
                "source_uri": source_uri,
                "document_id": document_id or str(uuid.uuid4())[:16],
                "metadata": metadata or {},
            }
        )
        resp.raise_for_status()
        return resp.json()
    
    def ingest_file(
        self,
        app_id: str,
        collection_id: str,
        file_path: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {
                "app_id": app_id,
                "collection_id": collection_id,
                "document_id": document_id or "",
                "metadata": str(metadata or {}),
            }
            resp = self.session.post(
                f"{self.base_url}/ingest/file",
                files=files,
                data=data,
            )
        resp.raise_for_status()
        return resp.json()
    
    def delete_document(self, app_id: str, collection_id: str, document_id: str) -> Dict[str, Any]:
        resp = self.session.delete(f"{self.base_url}/ingest/{app_id}/{collection_id}/{document_id}")
        resp.raise_for_status()
        return resp.json()
    
    # Search / Retrieval
    def search(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 10,
        filter_conditions: Optional[Dict[str, Any]] = None,
        use_hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        resp = self.session.post(f"{self.base_url}/search/", json={
            "query": query,
            "app_id": app_id,
            "collection_id": collection_id,
            "top_k": top_k,
            "filter_conditions": filter_conditions,
            "use_hybrid": use_hybrid,
        })
        resp.raise_for_status()
        return resp.json()["results"]
    
    def search_vector(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 10,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        resp = self.session.post(f"{self.base_url}/search/vector", json={
            "query": query,
            "app_id": app_id,
            "collection_id": collection_id,
            "top_k": top_k,
            "filter_conditions": filter_conditions,
        })
        resp.raise_for_status()
        return resp.json()["results"]
    
    def search_lexical(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        resp = self.session.post(f"{self.base_url}/search/lexical", json={
            "query": query,
            "app_id": app_id,
            "collection_id": collection_id,
            "top_k": top_k,
        })
        resp.raise_for_status()
        return resp.json()["results"]
    
    def get_context(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        resp = self.session.post(f"{self.base_url}/search/context", json={
            "query": query,
            "app_id": app_id,
            "collection_id": collection_id,
            "top_k": top_k,
            "filter_conditions": filter_conditions,
        })
        resp.raise_for_status()
        return resp.json()
    
    # Generation
    def ask(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        top_k: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        resp = self.session.post(f"{self.base_url}/generate/ask", json={
            "query": query,
            "app_id": app_id,
            "collection_id": collection_id,
            "top_k": top_k,
            "filter_conditions": filter_conditions,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        resp.raise_for_status()
        return resp.json()
    
    def list_generation_models(self) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/generate/models")
        resp.raise_for_status()
        return resp.json()
    
    # Feedback & Review
    def submit_feedback(
        self,
        app_id: str,
        collection_id: str,
        query: str,
        feedback_type: str,
        response: Optional[str] = None,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        rating: Optional[int] = None,
        explanation: Optional[str] = None,
    ) -> Dict[str, Any]:
        resp = self.session.post(f"{self.base_url}/feedback/", json={
            "app_id": app_id,
            "collection_id": collection_id,
            "query": query,
            "response": response,
            "retrieved_chunks": retrieved_chunks or [],
            "feedback_type": feedback_type,
            "rating": rating,
            "explanation": explanation,
        })
        resp.raise_for_status()
        return resp.json()
    
    def list_pending_reviews(self, app_id: str) -> List[Dict[str, Any]]:
        resp = self.session.get(f"{self.base_url}/feedback/{app_id}/pending")
        resp.raise_for_status()
        return resp.json()
    
    def list_all_reviews(self, app_id: str) -> List[Dict[str, Any]]:
        resp = self.session.get(f"{self.base_url}/feedback/{app_id}/all")
        resp.raise_for_status()
        return resp.json()
    
    def resolve_review(self, app_id: str, case_id: str, status: str, notes: str, reviewer_id: str) -> Dict[str, Any]:
        resp = self.session.post(f"{self.base_url}/feedback/{app_id}/cases/{case_id}/resolve", json={
            "status": status,
            "notes": notes,
            "reviewer_id": reviewer_id,
        })
        resp.raise_for_status()
        return resp.json()
    
    def create_annotation(
        self,
        app_id: str,
        collection_id: str,
        question: str,
        verified_answer: str,
        review_case_id: Optional[str] = None,
        source_refs: Optional[List[Dict[str, Any]]] = None,
        created_by: str = "admin",
    ) -> Dict[str, Any]:
        resp = self.session.post(f"{self.base_url}/feedback/annotations", json={
            "app_id": app_id,
            "collection_id": collection_id,
            "question": question,
            "verified_answer": verified_answer,
            "review_case_id": review_case_id,
            "source_refs": source_refs,
            "created_by": created_by,
        })
        resp.raise_for_status()
        return resp.json()
    
    def list_annotations(self, app_id: str, collection_id: str) -> List[Dict[str, Any]]:
        resp = self.session.get(f"{self.base_url}/feedback/annotations/{app_id}/{collection_id}")
        resp.raise_for_status()
        return resp.json()