import logging
import os
import json
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class GenerationResult:
    answer: str
    sources: List[Dict[str, Any]]
    model: str
    retrieval_results_count: int
    grounded: bool

class GenerationAdapter:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._available = None

    def check_availability(self) -> bool:
        """Check if the generation model endpoint is available."""
        if self._available is not None:
            return self._available
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                self._available = self.model in models
                return self._available
        except Exception:
            pass
        self._available = False
        return False

    def generate(
        self,
        query: str,
        context: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> GenerationResult:
        """Generate a grounded answer using retrieved context."""
        if not self.check_availability():
            raise RuntimeError(f"Generation model {self.model} not available at {self.base_url}")

        # Build prompt with strict grounding instructions
        system_prompt = """You are a precise assistant that answers questions ONLY using the provided context. 
Rules:
1. If the context does not contain the answer, state "I cannot answer based on the provided context."
2. Always cite sources using [Source X] format referencing the context sections.
3. Do not use external knowledge.
4. Be concise and factual."""
        
        user_prompt = f"""Context:
{context}

Question: {query}

Answer using only the context above. Cite sources as [Source 1], [Source 2], etc. If the context is insufficient, say so."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("message", {}).get("content", "")
            
            return GenerationResult(
                answer=answer,
                sources=[],  # Sources are tracked separately from context
                model=self.model,
                retrieval_results_count=0,
                grounded=True,
            )
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise

class OpenAICompatibleAdapter(GenerationAdapter):
    """Adapter for OpenAI-compatible endpoints (vLLM, LM Studio, etc.)."""
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "local-model",
        api_key: str = "not-needed",
        timeout: int = 120,
    ):
        super().__init__(base_url, model, timeout)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def check_availability(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        query: str,
        context: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> GenerationResult:
        if not self.check_availability():
            raise RuntimeError(f"Generation model not available at {self.base_url}")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Answer ONLY using the provided context. Cite sources as [Source X]. If context is insufficient, state that."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data["choices"][0]["message"]["content"]
            
            return GenerationResult(
                answer=answer,
                sources=[],
                model=self.model,
                retrieval_results_count=0,
                grounded=True,
            )
        except Exception as e:
            logger.error(f"OpenAI-compatible generation failed: {e}")
            raise


class RetrievalOnlyAdapter:
    """Dummy adapter that returns retrieved passages without generation."""
    
    def generate(self, query: str, context: str, max_tokens: int = 512, temperature: float = 0.1) -> GenerationResult:
        return GenerationResult(
            answer="[Retrieval-only mode] No generation model configured. Retrieved context:\n\n" + context,
            sources=[],
            model="retrieval-only",
            retrieval_results_count=0,
            grounded=True,
        )


class GenerationManager:
    """Manages generation adapters."""
    
    def __init__(self):
        self.adapters: Dict[str, GenerationAdapter] = {}
        self.default_adapter: Optional[str] = None

    def register_adapter(self, name: str, adapter: GenerationAdapter, default: bool = False):
        self.adapters[name] = adapter
        if default or self.default_adapter is None:
            self.default_adapter = name

    def get_adapter(self, name: Optional[str] = None) -> Optional[GenerationAdapter]:
        if name:
            return self.adapters.get(name)
        if self.default_adapter:
            return self.adapters[self.default_adapter]
        return RetrievalOnlyAdapter()

    def list_adapters(self) -> List[str]:
        return list(self.adapters.keys())