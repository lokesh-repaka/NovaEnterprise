"""Deterministic Fake LLM and Embeddings Provider for Offline Testing (N1, N2).

Generates reproducible completions, structured outputs, and normalized embeddings
with strictly zero external network calls or credentials.
"""

import hashlib
import json
import math
from typing import Any


class FakeLLM:
    """Mock LLM and Embedding provider operating completely offline."""

    def __init__(
        self, embedding_dim: int = 384, model_name: str = "fake-model"
    ) -> None:
        self.embedding_dim = embedding_dim
        self.model_name = model_name
        self.call_history: list[dict[str, Any]] = []
        self.custom_responses: dict[str, Any] = {}

    def set_response(self, key_pattern: str, response: Any) -> None:
        """Register a custom response for a specific prompt keyword or pattern."""
        self.custom_responses[key_pattern] = response

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate a deterministic completion based on the input prompt."""
        self.call_history.append(
            {"type": "complete", "prompt": prompt, "kwargs": kwargs}
        )

        for key, resp in self.custom_responses.items():
            if key in prompt:
                if isinstance(resp, str):
                    return resp
                return json.dumps(resp)

        # Deterministic default response synthesized from prompt keywords
        return f"[FakeLLM Response for '{prompt[:40]}...']: Synthesized enterprise reasoning and evidence."

    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a structured JSON output conforming to a provided schema."""
        self.call_history.append(
            {
                "type": "generate_structured",
                "prompt": prompt,
                "schema": schema,
                "kwargs": kwargs,
            }
        )

        for key, resp in self.custom_responses.items():
            if key in prompt and isinstance(resp, dict):
                return resp

        # Default structured object adhering to common agent analysis schemas
        if schema and "properties" in schema:
            output: dict[str, Any] = {}
            for prop_name, prop_spec in schema["properties"].items():
                prop_type = prop_spec.get("type", "string")
                if prop_type == "string":
                    output[prop_name] = f"mock_{prop_name}_val"
                elif prop_type == "integer":
                    output[prop_name] = 1
                elif prop_type == "number":
                    output[prop_name] = 1.0
                elif prop_type == "boolean":
                    output[prop_name] = True
                elif prop_type == "array":
                    output[prop_name] = []
                else:
                    output[prop_name] = None
            return output

        return {
            "entity": "Payments API",
            "complexity": "complex",
            "route": "hybrid",
            "confidence": 0.95,
        }

    def embed(self, text: str) -> list[float]:
        """Generate a deterministic, unit-normalized embedding vector for text."""
        # Hash text using SHA256 to create a reproducible pseudo-random seed
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed_ints = [b for b in digest]

        # Generate raw pseudo-vector of desired dimension
        raw_vec: list[float] = []
        for i in range(self.embedding_dim):
            byte_val = seed_ints[i % len(seed_ints)]
            # Deterministic variation across dimensions
            val = (byte_val ^ ((i * 31) & 0xFF)) / 128.0 - 1.0
            raw_vec.append(val)

        # L2-normalize vector so dot-product equals cosine similarity
        norm = math.sqrt(sum(x * x for x in raw_vec))
        if norm == 0.0:
            norm = 1.0
        return [round(x / norm, 6) for x in raw_vec]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch generate embeddings for multiple texts."""
        return [self.embed(t) for t in texts]

    def reset(self) -> None:
        """Clear recorded call history and custom response overrides."""
        self.call_history.clear()
        self.custom_responses.clear()
