# ABOUTME: ML model caching and optimization for FilterAgent and SummariseAgent
# ABOUTME: Provides GPU acceleration detection, model preloading, and memory-efficient caching

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import spacy
import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class ModelPerformanceMetrics:
    """Performance metrics for ML model operations."""

    load_time: float = 0.0
    inference_time: float = 0.0
    memory_usage_mb: float = 0.0
    gpu_available: bool = False
    gpu_used: bool = False
    model_size_mb: float = 0.0


class MLModelCache:
    """
    Optimized ML model cache with GPU acceleration and performance monitoring.

    Features:
    - Lazy loading with preloading option
    - GPU acceleration detection and utilization
    - Memory usage monitoring
    - Model lifecycle management
    - Performance metrics collection
    """

    def __init__(self):
        self._models: dict[str, Any] = {}
        self._metrics: dict[str, ModelPerformanceMetrics] = {}
        self._gpu_available = self._detect_gpu()
        self._initialization_lock = asyncio.Lock()

        logger.info(f"MLModelCache initialized. GPU available: {self._gpu_available}")

    def _detect_gpu(self) -> bool:
        """Detect if GPU acceleration is available."""
        try:
            # Check for CUDA
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
                logger.info(f"CUDA GPU detected: {gpu_name} (count: {gpu_count})")
                return True

            # Check for MPS (Apple Silicon)
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info("Apple MPS GPU detected")
                return True

            logger.info("No GPU acceleration available, using CPU")
            return False
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
            return False

    def _get_device(self) -> str:
        """Get the optimal device for model computation."""
        if self._gpu_available:
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        return "cpu"

    def _measure_memory_usage(self) -> float:
        """Measure current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)  # Convert to MB
        except ImportError:
            logger.warning("psutil not available for memory monitoring")
            return 0.0

    async def get_sentence_transformer(
        self, model_name: str = "all-MiniLM-L6-v2", use_gpu: bool = True
    ) -> SentenceTransformer:
        """
        Get optimized SentenceTransformer model with caching and GPU acceleration.

        Args:
            model_name: Name of the sentence transformer model
            use_gpu: Whether to use GPU acceleration if available

        Returns:
            Loaded and optimized SentenceTransformer model
        """
        cache_key = f"sentence_transformer_{model_name}"

        if cache_key in self._models:
            logger.debug(f"Using cached SentenceTransformer: {model_name}")
            return self._models[cache_key]

        async with self._initialization_lock:
            # Double-check after acquiring lock
            if cache_key in self._models:
                return self._models[cache_key]

            logger.info(f"Loading SentenceTransformer: {model_name}")
            start_time = time.time()
            memory_before = self._measure_memory_usage()

            try:
                # Load model in executor to avoid blocking
                def load_model():
                    device = self._get_device() if use_gpu else "cpu"
                    model = SentenceTransformer(model_name, device=device)

                    # Optimize model for inference
                    if hasattr(model, "_modules"):
                        for module in model._modules.values():
                            if hasattr(module, "eval"):
                                module.eval()

                    return model, device

                loop = asyncio.get_event_loop()
                model, device = await loop.run_in_executor(None, load_model)

                load_time = time.time() - start_time
                memory_after = self._measure_memory_usage()
                memory_usage = memory_after - memory_before

                # Store performance metrics
                self._metrics[cache_key] = ModelPerformanceMetrics(
                    load_time=load_time,
                    memory_usage_mb=memory_usage,
                    gpu_available=self._gpu_available,
                    gpu_used=(device != "cpu"),
                    model_size_mb=self._estimate_model_size(model),
                )

                # Cache the model
                self._models[cache_key] = model

                logger.info(
                    f"SentenceTransformer loaded successfully: {model_name} "
                    f"(device: {device}, load_time: {load_time:.2f}s, "
                    f"memory: {memory_usage:.1f}MB)"
                )

                return model

            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer {model_name}: {e}")
                raise

    async def get_spacy_model(
        self, model_name: str = "en_core_web_sm", fallback_to_blank: bool = True
    ) -> spacy.language.Language:
        """
        Get optimized spaCy model with caching and fallback options.

        Args:
            model_name: Name of the spaCy model
            fallback_to_blank: Whether to fallback to blank model if named model fails

        Returns:
            Loaded and optimized spaCy model
        """
        cache_key = f"spacy_{model_name}"

        if cache_key in self._models:
            logger.debug(f"Using cached spaCy model: {model_name}")
            return self._models[cache_key]

        async with self._initialization_lock:
            # Double-check after acquiring lock
            if cache_key in self._models:
                return self._models[cache_key]

            logger.info(f"Loading spaCy model: {model_name}")
            start_time = time.time()
            memory_before = self._measure_memory_usage()

            try:
                # Load model in executor to avoid blocking
                def load_model():
                    try:
                        nlp = spacy.load(model_name)
                        return nlp, model_name
                    except OSError as e:
                        if fallback_to_blank:
                            logger.warning(
                                f"spaCy model {model_name} not found, using blank model: {e}"
                            )
                            nlp = spacy.blank("en")
                            nlp.add_pipe("sentencizer")
                            return nlp, "en_blank"
                        else:
                            raise

                loop = asyncio.get_event_loop()
                model, actual_model_name = await loop.run_in_executor(None, load_model)

                load_time = time.time() - start_time
                memory_after = self._measure_memory_usage()
                memory_usage = memory_after - memory_before

                # Store performance metrics
                self._metrics[cache_key] = ModelPerformanceMetrics(
                    load_time=load_time,
                    memory_usage_mb=memory_usage,
                    gpu_available=False,  # spaCy doesn't use GPU for our use case
                    gpu_used=False,
                    model_size_mb=memory_usage,  # Approximate
                )

                # Cache the model
                self._models[cache_key] = model

                logger.info(
                    f"spaCy model loaded successfully: {actual_model_name} "
                    f"(load_time: {load_time:.2f}s, memory: {memory_usage:.1f}MB)"
                )

                return model

            except Exception as e:
                logger.error(f"Failed to load spaCy model {model_name}: {e}")
                raise

    def _estimate_model_size(self, model: Any) -> float:
        """Estimate model size in MB."""
        try:
            if hasattr(model, "get_sentence_embedding_dimension"):
                # SentenceTransformer - rough estimation
                return 90.0  # MiniLM is approximately 90MB
            return 0.0
        except Exception:
            return 0.0

    async def encode_texts_optimized(
        self,
        model: SentenceTransformer,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Optimized text encoding with batching and performance monitoring.

        Args:
            model: SentenceTransformer model
            texts: List of texts to encode
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            Encoded text embeddings
        """
        if not texts:
            return np.array([])

        start_time = time.time()

        try:
            # Use model's built-in batching for optimal performance
            def encode_batch():
                return model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=show_progress,
                    convert_to_numpy=True,
                    normalize_embeddings=True,  # Normalize for cosine similarity
                )

            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(None, encode_batch)

            inference_time = time.time() - start_time

            # Update metrics
            cache_key = (
                f"sentence_transformer_{model.get_sentence_embedding_dimension()}"
            )
            if cache_key in self._metrics:
                self._metrics[cache_key].inference_time = inference_time

            logger.debug(
                f"Encoded {len(texts)} texts in {inference_time:.2f}s "
                f"({len(texts) / inference_time:.1f} texts/sec)"
            )

            return embeddings

        except Exception as e:
            logger.error(f"Text encoding failed: {e}")
            raise

    async def preload_models(self) -> None:
        """Preload commonly used models for faster startup."""
        logger.info("Preloading ML models for optimal performance...")

        preload_tasks = [
            self.get_sentence_transformer("all-MiniLM-L6-v2"),
            self.get_spacy_model("en_core_web_sm"),
        ]

        try:
            await asyncio.gather(*preload_tasks, return_exceptions=True)
            logger.info("Model preloading completed")
        except Exception as e:
            logger.warning(f"Model preloading partially failed: {e}")

    def get_performance_metrics(self) -> dict[str, ModelPerformanceMetrics]:
        """Get performance metrics for all loaded models."""
        return self._metrics.copy()

    def get_cache_info(self) -> dict[str, Any]:
        """Get cache information and statistics."""
        return {
            "cached_models": list(self._models.keys()),
            "gpu_available": self._gpu_available,
            "device": self._get_device(),
            "cache_size": len(self._models),
            "total_memory_mb": sum(
                metrics.memory_usage_mb for metrics in self._metrics.values()
            ),
        }

    async def clear_cache(self) -> None:
        """Clear model cache and free memory."""
        logger.info("Clearing ML model cache...")

        # Clear GPU memory if using CUDA
        if self._gpu_available and torch.cuda.is_available():
            torch.cuda.empty_cache()

        self._models.clear()
        self._metrics.clear()

        logger.info("ML model cache cleared")


# Global instance
_model_cache: MLModelCache | None = None


def get_model_cache() -> MLModelCache:
    """Get the global ML model cache instance."""
    global _model_cache
    if _model_cache is None:
        _model_cache = MLModelCache()
    return _model_cache


async def initialize_model_cache() -> None:
    """Initialize and preload the ML model cache."""
    cache = get_model_cache()
    await cache.preload_models()


def clear_model_cache() -> None:
    """Clear the global ML model cache."""
    global _model_cache
    if _model_cache:
        asyncio.create_task(_model_cache.clear_cache())
        _model_cache = None
