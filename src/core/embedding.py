from typing import List, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

class EmbeddingProvider:
    """Wrapper for local embedding models using fastembed or sentence-transformers."""
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str = "cpu",
        batch_size: int = 32,
    ):
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model = None
        self._dim = None
        self._init_model()

    def _init_model(self):
        """Initialize the embedding model."""
        try:
            # Try fastembed first (optimized, no torch dependency at runtime)
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self.model_name)
            # Get dimension by encoding a test string
            test_emb = list(self._model.embed(["test"]))[0]
            self._dim = len(test_emb)
            logger.info(f"Initialized fastembed model: {self.model_name} (dim={self._dim})")
        except ImportError:
            # Fallback to sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                self._dim = self._model.get_sentence_embedding_dimension()
                logger.info(f"Initialized sentence-transformers model: {self.model_name} (dim={self._dim})")
            except ImportError:
                raise RuntimeError("Neither fastembed nor sentence-transformers available")

    @property
    def dimension(self) -> int:
        return self._dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode a list of texts into embeddings."""
        if not texts:
            return []
        
        if hasattr(self._model, 'embed'):
            # fastembed API
            embeddings = list(self._model.embed(texts, batch_size=self.batch_size))
            return [e.tolist() if hasattr(e, 'tolist') else list(e) for e in embeddings]
        else:
            # sentence-transformers API
            embeddings = self._model.encode(texts, batch_size=self.batch_size, show_progress_bar=False)
            return embeddings.tolist() if hasattr(embeddings, 'tolist') else [list(e) for e in embeddings]

    def encode_single(self, text: str) -> List[float]:
        """Encode a single text."""
        return self.encode([text])[0]


class EmbeddingRegistry:
    """Registry of available embedding models with metadata."""
    
    KNOWN_MODELS = {
        "BAAI/bge-small-en-v1.5": {
            "dim": 384,
            "max_tokens": 512,
            "languages": ["en"],
            "description": "Compact English embedding model, fast and efficient",
            "license": "MIT",
            "size_mb": 134,
        },
        "BAAI/bge-base-en-v1.5": {
            "dim": 768,
            "max_tokens": 512,
            "languages": ["en"],
            "description": "Base English embedding model, higher quality",
            "license": "MIT",
            "size_mb": 440,
        },
        "BAAI/bge-large-en-v1.5": {
            "dim": 1024,
            "max_tokens": 512,
            "languages": ["en"],
            "description": "Large English embedding model, best quality",
            "license": "MIT",
            "size_mb": 1340,
        },
        "sentence-transformers/all-MiniLM-L6-v2": {
            "dim": 384,
            "max_tokens": 256,
            "languages": ["en"],
            "description": "Lightweight general-purpose embedding",
            "license": "Apache-2.0",
            "size_mb": 90,
        },
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": {
            "dim": 384,
            "max_tokens": 128,
            "languages": ["en", "de", "fr", "es", "it", "nl", "pt", "ru", "zh", "ja", "ko"],
            "description": "Multilingual embedding model",
            "license": "Apache-2.0",
            "size_mb": 420,
        },
    }

    @classmethod
    def get_model_info(cls, model_name: str) -> Optional[Dict[str, Any]]:
        return cls.KNOWN_MODELS.get(model_name)

    @classmethod
    def list_models(cls) -> Dict[str, Dict[str, Any]]:
        return cls.KNOWN_MODELS.copy()

    @classmethod
    def is_model_supported(cls, model_name: str) -> bool:
        return model_name in cls.KNOWN_MODELS