#!/usr/bin/env python3
"""
Semantic Embedding Generation with Caching
AGENT_GURU - Task 5 Implementation

MAXIMUM ENGINEERING MANDATE (ZERO COMPROMISE):
- Complete semantic embedding generation with dimensionality reduction and clustering
- Full optimization with caching, batching, and memory efficiency
- Production standards: Must handle embedding generation ≤50ms per text segment

Extracted algorithms from Sentence Transformers repository:
- Semantic embedding generation mathematics
- Similarity computation algorithms with approximate nearest neighbor search
- Dimensionality reduction techniques with PCA and t-SNE
- Cross-lingual embedding methods with alignment
- Vector storage and retrieval optimization

Performance Requirements:
- Embedding generation: ≤50ms per text segment (with batching optimization)
- Similarity computation: <10ms for 1M+ vectors with approximate search
- Memory efficiency: Compressed embeddings with minimal quality loss
"""

import hashlib
import json
import math
import os
import pickle
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import warnings

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
import faiss  # For approximate nearest neighbor search

warnings.filterwarnings("ignore", category=UserWarning)

@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation"""
    model_name: str = "sentence-transformer"
    embedding_dim: int = 768
    max_seq_length: int = 512
    normalize_embeddings: bool = True
    use_cache: bool = True
    cache_dir: str = "embeddings_cache"
    batch_size: int = 32
    device: str = "auto"
    
    # Compression settings
    use_compression: bool = False
    compression_dim: int = 256
    compression_method: str = "pca"  # "pca", "svd", "autoencoder"
    
    # Similarity search settings
    similarity_metric: str = "cosine"  # "cosine", "euclidean", "dot_product"
    use_approximate_search: bool = True
    index_type: str = "IVF"  # "Flat", "IVF", "HNSW"

@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    embeddings: np.ndarray
    texts: List[str]
    generation_time_ms: float
    cache_hit: bool = False
    compressed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

class EmbeddingCache:
    """Thread-safe cache for embeddings with LRU eviction"""
    
    def __init__(self, cache_dir: str, max_size: int = 10000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size = max_size
        self._lock = threading.RLock()
        self._access_times = {}
        self._cache_index = self._load_cache_index()
    
    def _load_cache_index(self) -> Dict[str, Dict]:
        """Load cache index from disk"""
        index_file = self.cache_dir / "cache_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_cache_index(self):
        """Save cache index to disk"""
        index_file = self.cache_dir / "cache_index.json"
        try:
            with open(index_file, 'w') as f:
                json.dump(self._cache_index, f)
        except Exception:
            pass  # Fail silently for cache operations
    
    def _get_cache_key(self, text: str, model_name: str) -> str:
        """Generate cache key for text and model"""
        content = f"{model_name}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get(self, text: str, model_name: str) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        with self._lock:
            cache_key = self._get_cache_key(text, model_name)
            
            if cache_key not in self._cache_index:
                return None
            
            cache_file = self.cache_dir / f"{cache_key}.npy"
            if not cache_file.exists():
                # Remove stale index entry
                del self._cache_index[cache_key]
                return None
            
            try:
                embedding = np.load(cache_file)
                self._access_times[cache_key] = time.time()
                return embedding
            except Exception:
                return None
    
    def put(self, text: str, model_name: str, embedding: np.ndarray):
        """Store embedding in cache"""
        with self._lock:
            cache_key = self._get_cache_key(text, model_name)
            
            # Check if cache is full and evict LRU entries
            if len(self._cache_index) >= self.max_size:
                self._evict_lru()
            
            # Save embedding to disk
            cache_file = self.cache_dir / f"{cache_key}.npy"
            try:
                np.save(cache_file, embedding)
                
                # Update index
                self._cache_index[cache_key] = {
                    "text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
                    "model_name": model_name,
                    "timestamp": time.time(),
                    "embedding_shape": embedding.shape
                }
                self._access_times[cache_key] = time.time()
                
                # Save index periodically
                if len(self._cache_index) % 100 == 0:
                    self._save_cache_index()
                    
            except Exception:
                pass  # Fail silently for cache operations
    
    def _evict_lru(self):
        """Evict least recently used entries"""
        if not self._access_times:
            return
        
        # Find LRU entries
        sorted_entries = sorted(self._access_times.items(), key=lambda x: x[1])
        entries_to_evict = sorted_entries[:len(sorted_entries) // 4]  # Evict 25%
        
        for cache_key, _ in entries_to_evict:
            # Remove file
            cache_file = self.cache_dir / f"{cache_key}.npy"
            if cache_file.exists():
                cache_file.unlink()
            
            # Remove from index
            if cache_key in self._cache_index:
                del self._cache_index[cache_key]
            if cache_key in self._access_times:
                del self._access_times[cache_key]
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            # Remove all cache files
            for cache_file in self.cache_dir.glob("*.npy"):
                cache_file.unlink()
            
            # Clear indices
            self._cache_index.clear()
            self._access_times.clear()
            self._save_cache_index()

class TextEncoder(nn.Module):
    """
    Text encoder for generating embeddings
    Simplified implementation - production would use actual transformer
    """
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__()
        self.config = config
        self.embedding_dim = config.embedding_dim
        
        # Simplified encoder layers
        self.embedding = nn.Embedding(30000, config.embedding_dim)  # Vocab size
        self.positional_encoding = nn.Embedding(config.max_seq_length, config.embedding_dim)
        
        # Transformer-like layers (simplified)
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=config.embedding_dim,
                nhead=12,
                dim_feedforward=config.embedding_dim * 4,
                dropout=0.1,
                batch_first=True
            ) for _ in range(6)
        ])
        
        # Pooling layer
        self.pooler = nn.Linear(config.embedding_dim, config.embedding_dim)
        self.pooler_activation = nn.Tanh()
    
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Forward pass to generate embeddings"""
        seq_len = input_ids.size(1)
        
        # Token embeddings
        token_embeddings = self.embedding(input_ids)
        
        # Positional embeddings
        position_ids = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)
        position_embeddings = self.positional_encoding(position_ids)
        
        # Combine embeddings
        embeddings = token_embeddings + position_embeddings
        
        # Apply transformer layers
        for layer in self.layers:
            embeddings = layer(embeddings, src_key_padding_mask=~attention_mask.bool())
        
        # Mean pooling with attention mask
        masked_embeddings = embeddings * attention_mask.unsqueeze(-1)
        pooled = masked_embeddings.sum(dim=1) / attention_mask.sum(dim=1, keepdim=True)
        
        # Apply pooler
        pooled = self.pooler(pooled)
        pooled = self.pooler_activation(pooled)
        
        return pooled

class DimensionalityReducer:
    """Dimensionality reduction for embedding compression"""
    
    def __init__(self, method: str = "pca", target_dim: int = 256):
        self.method = method
        self.target_dim = target_dim
        self.reducer = None
        self.is_fitted = False
    
    def fit(self, embeddings: np.ndarray) -> 'DimensionalityReducer':
        """Fit dimensionality reducer on embeddings"""
        if self.method == "pca":
            self.reducer = PCA(n_components=self.target_dim, random_state=42)
        elif self.method == "svd":
            self.reducer = TruncatedSVD(n_components=self.target_dim, random_state=42)
        elif self.method == "tsne":
            self.reducer = TSNE(n_components=min(self.target_dim, 3), random_state=42)
        else:
            raise ValueError(f"Unknown reduction method: {self.method}")
        
        self.reducer.fit(embeddings)
        self.is_fitted = True
        return self
    
    def transform(self, embeddings: np.ndarray) -> np.ndarray:
        """Transform embeddings to reduced dimensions"""
        if not self.is_fitted:
            raise ValueError("Reducer must be fitted before transform")
        
        return self.reducer.transform(embeddings)
    
    def fit_transform(self, embeddings: np.ndarray) -> np.ndarray:
        """Fit and transform embeddings"""
        return self.fit(embeddings).transform(embeddings)
    
    def get_explained_variance_ratio(self) -> Optional[np.ndarray]:
        """Get explained variance ratio for PCA/SVD"""
        if hasattr(self.reducer, 'explained_variance_ratio_'):
            return self.reducer.explained_variance_ratio_
        return None

class SimilarityIndex:
    """Efficient similarity search index using FAISS"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.index = None
        self.embeddings = None
        self.texts = []
        self.embedding_dim = config.embedding_dim
        
        # Initialize FAISS index
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize FAISS index based on configuration"""
        if self.config.index_type == "Flat":
            if self.config.similarity_metric == "cosine":
                self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine
            else:
                self.index = faiss.IndexFlatL2(self.embedding_dim)  # L2 for euclidean
        
        elif self.config.index_type == "IVF":
            # IVF index for faster search on large datasets
            nlist = 100  # Number of clusters
            quantizer = faiss.IndexFlatL2(self.embedding_dim)
            self.index = faiss.IndexIVFFlat(quantizer, self.embedding_dim, nlist)
        
        elif self.config.index_type == "HNSW":
            # HNSW index for very fast approximate search
            self.index = faiss.IndexHNSWFlat(self.embedding_dim, 32)
        
        else:
            raise ValueError(f"Unknown index type: {self.config.index_type}")
    
    def add_embeddings(self, embeddings: np.ndarray, texts: List[str]):
        """Add embeddings to the index"""
        if embeddings.shape[1] != self.embedding_dim:
            raise ValueError(f"Embedding dimension mismatch: {embeddings.shape[1]} vs {self.embedding_dim}")
        
        # Normalize embeddings for cosine similarity
        if self.config.similarity_metric == "cosine":
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        # Train index if needed (for IVF)
        if hasattr(self.index, 'is_trained') and not self.index.is_trained:
            self.index.train(embeddings.astype(np.float32))
        
        # Add to index
        self.index.add(embeddings.astype(np.float32))
        
        # Store embeddings and texts
        if self.embeddings is None:
            self.embeddings = embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings])
        
        self.texts.extend(texts)
    
    def search(self, query_embeddings: np.ndarray, k: int = 10, threshold: float = 0.7) -> List[Tuple[List[int], List[float]]]:
        """Search for similar embeddings"""
        if self.index.ntotal == 0:
            return []
        
        # Normalize query embeddings for cosine similarity
        if self.config.similarity_metric == "cosine":
            query_embeddings = query_embeddings / np.linalg.norm(query_embeddings, axis=1, keepdims=True)
        
        # Search
        scores, indices = self.index.search(query_embeddings.astype(np.float32), k)
        
        results = []
        for i in range(len(query_embeddings)):
            # Filter by threshold
            valid_indices = []
            valid_scores = []
            
            for idx, score in zip(indices[i], scores[i]):
                if idx != -1:  # Valid index
                    # Convert distance to similarity for L2
                    if self.config.similarity_metric != "cosine":
                        similarity = 1.0 / (1.0 + score)  # Convert distance to similarity
                    else:
                        similarity = score
                    
                    if similarity >= threshold:
                        valid_indices.append(idx)
                        valid_scores.append(similarity)
            
            results.append((valid_indices, valid_scores))
        
        return results
    
    def get_texts_by_indices(self, indices: List[int]) -> List[str]:
        """Get texts corresponding to indices"""
        return [self.texts[i] for i in indices if 0 <= i < len(self.texts)]

class SemanticEmbeddingGenerator:
    """
    Production-grade semantic embedding generator with caching and optimization
    """
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.device = self._get_device(config.device)
        
        # Initialize components
        self.encoder = TextEncoder(config).to(self.device)
        self.cache = EmbeddingCache(config.cache_dir) if config.use_cache else None
        self.similarity_index = SimilarityIndex(config)
        self.dimensionality_reducer = None
        
        # Thread pool for batch processing
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Performance tracking
        self.generation_times = []
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Set to evaluation mode
        self.encoder.eval()
    
    def _get_device(self, device: str) -> torch.device:
        """Get the best available device"""
        if device == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return torch.device("mps")
            else:
                return torch.device("cpu")
        return torch.device(device)
    
    def _tokenize_texts(self, texts: List[str]) -> Tuple[torch.Tensor, torch.Tensor]:
        """Tokenize texts for encoding (simplified implementation)"""
        # Simplified tokenization - production would use actual tokenizer
        max_len = self.config.max_seq_length
        
        input_ids = []
        attention_masks = []
        
        for text in texts:
            # Simple word-based tokenization (production would use subword)
            words = text.lower().split()[:max_len-2]  # Leave space for special tokens
            
            # Convert to IDs (simplified)
            token_ids = [1]  # CLS token
            for word in words:
                # Simple hash-based ID generation
                token_id = hash(word) % 29998 + 2  # Avoid special tokens
                token_ids.append(token_id)
            token_ids.append(2)  # SEP token
            
            # Pad to max length
            attention_mask = [1] * len(token_ids) + [0] * (max_len - len(token_ids))
            token_ids = token_ids + [0] * (max_len - len(token_ids))
            
            input_ids.append(token_ids[:max_len])
            attention_masks.append(attention_mask[:max_len])
        
        return (
            torch.tensor(input_ids, dtype=torch.long, device=self.device),
            torch.tensor(attention_masks, dtype=torch.long, device=self.device)
        )
    
    def generate_embeddings(
        self,
        texts: List[str],
        use_cache: Optional[bool] = None,
        batch_size: Optional[int] = None
    ) -> EmbeddingResult:
        """
        Generate embeddings for texts with caching and batching
        
        Args:
            texts: List of texts to encode
            use_cache: Override cache usage setting
            batch_size: Override batch size setting
        
        Returns:
            EmbeddingResult with embeddings and metadata
        """
        start_time = time.time()
        
        use_cache = use_cache if use_cache is not None else self.config.use_cache
        batch_size = batch_size if batch_size is not None else self.config.batch_size
        
        embeddings = []
        cache_hits = 0
        
        # Check cache for each text
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            if use_cache and self.cache:
                cached_embedding = self.cache.get(text, self.config.model_name)
                if cached_embedding is not None:
                    embeddings.append(cached_embedding)
                    cache_hits += 1
                    continue
            
            embeddings.append(None)  # Placeholder
            uncached_texts.append(text)
            uncached_indices.append(i)
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            uncached_embeddings = self._generate_embeddings_batch(
                uncached_texts, batch_size
            )
            
            # Store in cache and update results
            for i, (text, embedding) in enumerate(zip(uncached_texts, uncached_embeddings)):
                result_index = uncached_indices[i]
                embeddings[result_index] = embedding
                
                if use_cache and self.cache:
                    self.cache.put(text, self.config.model_name, embedding)
        
        # Convert to numpy array
        final_embeddings = np.array(embeddings)
        
        # Apply compression if enabled
        compressed = False
        if self.config.use_compression:
            final_embeddings = self._compress_embeddings(final_embeddings)
            compressed = True
        
        # Normalize if required
        if self.config.normalize_embeddings:
            final_embeddings = final_embeddings / np.linalg.norm(
                final_embeddings, axis=1, keepdims=True
            )
        
        generation_time = (time.time() - start_time) * 1000  # Convert to ms
        self.generation_times.append(generation_time)
        self.cache_hits += cache_hits
        self.cache_misses += len(uncached_texts)
        
        return EmbeddingResult(
            embeddings=final_embeddings,
            texts=texts,
            generation_time_ms=generation_time,
            cache_hit=cache_hits > 0,
            compressed=compressed,
            metadata={
                "cache_hits": cache_hits,
                "cache_misses": len(uncached_texts),
                "batch_size": batch_size,
                "device": str(self.device),
                "normalized": self.config.normalize_embeddings
            }
        )
    
    def _generate_embeddings_batch(self, texts: List[str], batch_size: int) -> np.ndarray:
        """Generate embeddings for a batch of texts"""
        all_embeddings = []
        
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Tokenize batch
                input_ids, attention_mask = self._tokenize_texts(batch_texts)
                
                # Generate embeddings
                batch_embeddings = self.encoder(input_ids, attention_mask)
                
                # Convert to numpy
                batch_embeddings = batch_embeddings.cpu().numpy()
                all_embeddings.append(batch_embeddings)
        
        return np.vstack(all_embeddings)
    
    def _compress_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """Compress embeddings using dimensionality reduction"""
        if self.dimensionality_reducer is None:
            self.dimensionality_reducer = DimensionalityReducer(
                method=self.config.compression_method,
                target_dim=self.config.compression_dim
            )
            self.dimensionality_reducer.fit(embeddings)
        
        return self.dimensionality_reducer.transform(embeddings)
    
    def compute_similarity(
        self,
        embeddings1: np.ndarray,
        embeddings2: np.ndarray,
        metric: Optional[str] = None
    ) -> np.ndarray:
        """
        Compute similarity between embeddings with advanced metrics
        Enhanced with similarity functions from sentence-transformers
        """
        metric = metric or self.config.similarity_metric
        
        # Convert to torch tensors for optimized computation
        emb1_tensor = torch.from_numpy(embeddings1).float()
        emb2_tensor = torch.from_numpy(embeddings2).float()
        
        if metric == "cosine":
            # Optimized cosine similarity with numerical stability
            emb1_norm = F.normalize(emb1_tensor, p=2, dim=1)
            emb2_norm = F.normalize(emb2_tensor, p=2, dim=1)
            similarity = torch.mm(emb1_norm, emb2_norm.t())
            
        elif metric == "euclidean":
            # Euclidean distance converted to similarity
            # Using broadcasting for efficiency
            diff = emb1_tensor.unsqueeze(1) - emb2_tensor.unsqueeze(0)
            distances = torch.norm(diff, p=2, dim=2)
            # Convert distance to similarity: sim = 1 / (1 + dist)
            similarity = 1.0 / (1.0 + distances)
            
        elif metric == "manhattan":
            # Manhattan distance converted to similarity
            diff = emb1_tensor.unsqueeze(1) - emb2_tensor.unsqueeze(0)
            distances = torch.norm(diff, p=1, dim=2)
            similarity = 1.0 / (1.0 + distances)
            
        elif metric == "dot_product":
            # Dot product similarity
            similarity = torch.mm(emb1_tensor, emb2_tensor.t())
            
        elif metric == "angular":
            # Angular similarity (cosine distance converted to angle)
            emb1_norm = F.normalize(emb1_tensor, p=2, dim=1)
            emb2_norm = F.normalize(emb2_tensor, p=2, dim=1)
            cosine_sim = torch.mm(emb1_norm, emb2_norm.t())
            # Convert to angular similarity: 1 - (arccos(cosine_sim) / π)
            angles = torch.acos(torch.clamp(cosine_sim, -1.0, 1.0))
            similarity = 1.0 - (angles / math.pi)
            
        elif metric == "pearson":
            # Pearson correlation coefficient
            def pearson_correlation(x, y):
                x_centered = x - x.mean(dim=1, keepdim=True)
                y_centered = y - y.mean(dim=1, keepdim=True)
                
                numerator = torch.mm(x_centered, y_centered.t())
                x_std = torch.norm(x_centered, p=2, dim=1, keepdim=True)
                y_std = torch.norm(y_centered, p=2, dim=1, keepdim=True)
                denominator = torch.mm(x_std, y_std.t())
                
                return numerator / (denominator + 1e-8)
            
            similarity = pearson_correlation(emb1_tensor, emb2_tensor)
            
        else:
            raise ValueError(f"Unknown similarity metric: {metric}")
        
        return similarity.numpy()
    
    def compute_pairwise_similarity(
        self,
        embeddings1: np.ndarray,
        embeddings2: np.ndarray,
        metric: Optional[str] = None
    ) -> np.ndarray:
        """
        Compute pairwise similarity (diagonal only) for efficiency
        Based on sentence-transformers pairwise functions
        """
        metric = metric or self.config.similarity_metric
        
        if embeddings1.shape[0] != embeddings2.shape[0]:
            raise ValueError("Embeddings must have same batch size for pairwise similarity")
        
        # Convert to torch tensors
        emb1_tensor = torch.from_numpy(embeddings1).float()
        emb2_tensor = torch.from_numpy(embeddings2).float()
        
        if metric == "cosine":
            # Pairwise cosine similarity
            emb1_norm = F.normalize(emb1_tensor, p=2, dim=1)
            emb2_norm = F.normalize(emb2_tensor, p=2, dim=1)
            similarity = torch.sum(emb1_norm * emb2_norm, dim=1)
            
        elif metric == "euclidean":
            # Pairwise euclidean distance
            distances = torch.norm(emb1_tensor - emb2_tensor, p=2, dim=1)
            similarity = 1.0 / (1.0 + distances)
            
        elif metric == "manhattan":
            # Pairwise manhattan distance
            distances = torch.norm(emb1_tensor - emb2_tensor, p=1, dim=1)
            similarity = 1.0 / (1.0 + distances)
            
        elif metric == "dot_product":
            # Pairwise dot product
            similarity = torch.sum(emb1_tensor * emb2_tensor, dim=1)
            
        else:
            raise ValueError(f"Unknown similarity metric: {metric}")
        
        return similarity.numpy()
    
    def find_similar_texts(
        self,
        query_texts: List[str],
        candidate_texts: List[str],
        k: int = 10,
        threshold: float = 0.7
    ) -> List[Tuple[List[str], List[float]]]:
        """Find similar texts using semantic search"""
        # Generate embeddings
        query_result = self.generate_embeddings(query_texts)
        candidate_result = self.generate_embeddings(candidate_texts)
        
        # Add candidates to index if not already present
        if self.similarity_index.index.ntotal == 0:
            self.similarity_index.add_embeddings(
                candidate_result.embeddings,
                candidate_texts
            )
        
        # Search for similar texts
        search_results = self.similarity_index.search(
            query_result.embeddings, k, threshold
        )
        
        # Convert indices to texts
        final_results = []
        for indices, scores in search_results:
            similar_texts = self.similarity_index.get_texts_by_indices(indices)
            final_results.append((similar_texts, scores))
        
        return final_results
    
    def cluster_texts(
        self,
        texts: List[str],
        n_clusters: int = 5,
        method: str = "kmeans"
    ) -> Tuple[List[int], np.ndarray]:
        """Cluster texts based on semantic similarity"""
        # Generate embeddings
        result = self.generate_embeddings(texts)
        embeddings = result.embeddings
        
        # Perform clustering
        if method == "kmeans":
            clusterer = KMeans(n_clusters=n_clusters, random_state=42)
        elif method == "dbscan":
            clusterer = DBSCAN(eps=0.5, min_samples=2)
        else:
            raise ValueError(f"Unknown clustering method: {method}")
        
        cluster_labels = clusterer.fit_predict(embeddings)
        
        # Get cluster centers if available
        cluster_centers = None
        if hasattr(clusterer, 'cluster_centers_'):
            cluster_centers = clusterer.cluster_centers_
        
        return cluster_labels.tolist(), cluster_centers
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        if not self.generation_times:
            return {"status": "no_data"}
        
        total_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            "total_generations": len(self.generation_times),
            "average_time_ms": sum(self.generation_times) / len(self.generation_times),
            "max_time_ms": max(self.generation_times),
            "min_time_ms": min(self.generation_times),
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "device": str(self.device),
            "index_size": self.similarity_index.index.ntotal if self.similarity_index.index else 0
        }
    
    def save_model(self, path: str):
        """Save model and configuration"""
        save_path = Path(path)
        save_path.mkdir(exist_ok=True)
        
        # Save model state
        torch.save(self.encoder.state_dict(), save_path / "encoder.pt")
        
        # Save configuration
        with open(save_path / "config.json", 'w') as f:
            json.dump(self.config.__dict__, f, indent=2)
        
        # Save dimensionality reducer if fitted
        if self.dimensionality_reducer and self.dimensionality_reducer.is_fitted:
            with open(save_path / "reducer.pkl", 'wb') as f:
                pickle.dump(self.dimensionality_reducer, f)
    
    def load_model(self, path: str):
        """Load model and configuration"""
        load_path = Path(path)
        
        # Load model state
        model_file = load_path / "encoder.pt"
        if model_file.exists():
            self.encoder.load_state_dict(torch.load(model_file, map_location=self.device))
        
        # Load dimensionality reducer
        reducer_file = load_path / "reducer.pkl"
        if reducer_file.exists():
            with open(reducer_file, 'rb') as f:
                self.dimensionality_reducer = pickle.load(f)

# Factory function
def create_embedding_generator(config: EmbeddingConfig) -> SemanticEmbeddingGenerator:
    """Create and initialize embedding generator"""
    return SemanticEmbeddingGenerator(config)

if __name__ == "__main__":
    # Example usage
    config = EmbeddingConfig(
        embedding_dim=256,
        batch_size=16,
        use_cache=True,
        use_compression=True,
        compression_dim=128
    )
    
    generator = create_embedding_generator(config)
    
    # Test embedding generation
    texts = [
        "The quick brown fox jumps over the lazy dog",
        "A fast brown fox leaps over a sleepy dog",
        "Machine learning is a subset of artificial intelligence",
        "Deep learning uses neural networks with multiple layers"
    ]
    
    result = generator.generate_embeddings(texts)
    print(f"Generated embeddings shape: {result.embeddings.shape}")
    print(f"Generation time: {result.generation_time_ms:.2f}ms")
    print(f"Cache hit: {result.cache_hit}")
    
    # Test similarity search
    query_texts = ["A brown fox jumps"]
    similar_results = generator.find_similar_texts(query_texts, texts, k=2)
    
    print(f"\nSimilar texts to '{query_texts[0]}':")
    for text, score in zip(similar_results[0][0], similar_results[0][1]):
        print(f"  {text}: {score:.3f}")
    
    # Test clustering
    cluster_labels, centers = generator.cluster_texts(texts, n_clusters=2)
    print(f"\nCluster labels: {cluster_labels}")
    
    # Performance metrics
    metrics = generator.get_performance_metrics()
    print(f"\nPerformance metrics: {metrics}")