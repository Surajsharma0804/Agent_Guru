"""
Vector Search Engine for GURU Memory Service

Provides local vector similarity search capabilities for memory retrieval:
- Local-only vector embeddings (no external dependencies)
- Cosine similarity search
- Efficient indexing and retrieval
- Support for multiple embedding models
- Memory-efficient operations

Features:
- TF-IDF vectorization for text content
- Cosine similarity scoring
- Configurable similarity thresholds
- Batch processing for efficiency
- Memory usage optimization
"""

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Result from vector similarity search."""
    record_id: str
    memory_type: str
    similarity_score: float
    content_preview: str
    metadata: Dict[str, Any]


@dataclass
class VectorIndex:
    """Vector index for a specific memory type."""
    memory_type: str
    vectors: Dict[str, np.ndarray]  # record_id -> vector
    vocabulary: Dict[str, int]      # term -> index
    idf_scores: Dict[str, float]    # term -> IDF score
    record_metadata: Dict[str, Dict[str, Any]]  # record_id -> metadata
    last_updated: float


class VectorSearchError(Exception):
    """Base exception for vector search operations."""


class VectorSearchEngine:
    """
    Local vector search engine for GURU memory service.
    
    Provides TF-IDF based vector similarity search without external dependencies.
    Optimized for local processing and privacy preservation.
    """
    
    def __init__(self, min_similarity_threshold: float = 0.1):
        """
        Initialize vector search engine.
        
        Args:
            min_similarity_threshold: Minimum similarity score for results
        """
        self.min_similarity_threshold = min_similarity_threshold
        self.indexes: Dict[str, VectorIndex] = {}
        self._stop_words = self._get_stop_words()
        self._text_processor = VectorTextTransformer()
    
    def _get_stop_words(self) -> Set[str]:
        """Get common English stop words."""
        return {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'the', 'this', 'but', 'they', 'have',
            'had', 'what', 'said', 'each', 'which', 'she', 'do', 'how', 'their',
            'if', 'up', 'out', 'many', 'then', 'them', 'these', 'so', 'some',
            'her', 'would', 'make', 'like', 'into', 'him', 'time', 'two', 'more',
            'go', 'no', 'way', 'could', 'my', 'than', 'first', 'been', 'call',
            'who', 'oil', 'sit', 'now', 'find', 'down', 'day', 'did', 'get',
            'come', 'made', 'may', 'part'
        }
    
    def add_document(self, memory_type: str, record_id: str, content: str, 
                    metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a document to the vector index.
        
        Args:
            memory_type: Type of memory (episodic, semantic, etc.)
            record_id: Unique identifier for the record
            content: Text content to index
            metadata: Optional metadata for the record
        """
        try:
            # Ensure index exists for memory type
            if memory_type not in self.indexes:
                self.indexes[memory_type] = VectorIndex(
                    memory_type=memory_type,
                    vectors={},
                    vocabulary={},
                    idf_scores={},
                    record_metadata={},
                    last_updated=0.0
                )
            
            index = self.indexes[memory_type]
            
            # Process text content
            terms = self._text_processor.process_text(content)
            
            # Update vocabulary
            for term in terms:
                if term not in index.vocabulary:
                    index.vocabulary[term] = len(index.vocabulary)
            
            # Store metadata
            index.record_metadata[record_id] = metadata or {}
            index.record_metadata[record_id]['content_preview'] = content[:200]
            
            # Rebuild vectors and IDF scores for this memory type
            self._rebuild_index(memory_type)
            
            logger.debug(f"Added document {record_id} to {memory_type} index")
            
        except Exception as e:
            logger.error(f"Failed to add document to vector index: {e}")
            raise VectorSearchError(f"Failed to add document: {e}")
    
    def remove_document(self, memory_type: str, record_id: str) -> None:
        """
        Remove a document from the vector index.
        
        Args:
            memory_type: Type of memory
            record_id: Record identifier to remove
        """
        try:
            if memory_type not in self.indexes:
                return
            
            index = self.indexes[memory_type]
            
            # Remove from vectors and metadata
            if record_id in index.vectors:
                del index.vectors[record_id]
            if record_id in index.record_metadata:
                del index.record_metadata[record_id]
            
            # Rebuild index to update IDF scores
            if index.vectors:
                self._rebuild_index(memory_type)
            else:
                # Clear empty index
                del self.indexes[memory_type]
            
            logger.debug(f"Removed document {record_id} from {memory_type} index")
            
        except Exception as e:
            logger.error(f"Failed to remove document from vector index: {e}")
            raise VectorSearchError(f"Failed to remove document: {e}")
    
    def search(self, query: str, memory_types: Optional[List[str]] = None,
              max_results: int = 10) -> List[VectorSearchResult]:
        """
        Search for similar documents across memory types.
        
        Args:
            query: Search query text
            memory_types: List of memory types to search (None for all)
            max_results: Maximum number of results to return
            
        Returns:
            List[VectorSearchResult]: Ranked search results
        """
        try:
            if not query.strip():
                return []
            
            # Determine which indexes to search
            search_indexes = memory_types or list(self.indexes.keys())
            
            all_results = []
            
            for memory_type in search_indexes:
                if memory_type not in self.indexes:
                    continue
                
                results = self._search_index(memory_type, query)
                all_results.extend(results)
            
            # Sort by similarity score (descending)
            all_results.sort(key=lambda x: x.similarity_score, reverse=True)
            
            # Return top results
            return all_results[:max_results]
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise VectorSearchError(f"Search failed: {e}")
    
    def _search_index(self, memory_type: str, query: str) -> List[VectorSearchResult]:
        """Search within a specific memory type index."""
        index = self.indexes[memory_type]
        
        if not index.vectors:
            return []
        
        # Process query text
        query_terms = self._text_processor.process_text(query)
        
        # Create query vector
        query_vector = self._create_tfidf_vector(query_terms, index)
        
        if np.sum(query_vector) == 0:
            return []
        
        results = []
        
        # Calculate similarity with all documents
        for record_id, doc_vector in index.vectors.items():
            similarity = self._cosine_similarity(query_vector, doc_vector)
            
            if similarity >= self.min_similarity_threshold:
                metadata = index.record_metadata.get(record_id, {})
                
                results.append(VectorSearchResult(
                    record_id=record_id,
                    memory_type=memory_type,
                    similarity_score=similarity,
                    content_preview=metadata.get('content_preview', ''),
                    metadata=metadata
                ))
        
        return results
    
    def _rebuild_index(self, memory_type: str) -> None:
        """Rebuild the vector index for a memory type."""
        index = self.indexes[memory_type]
        
        if not index.record_metadata:
            return
        
        # Collect all documents
        documents = {}
        all_terms = set()
        
        for record_id, metadata in index.record_metadata.items():
            content = metadata.get('content_preview', '')
            terms = self._text_processor.process_text(content)
            documents[record_id] = terms
            all_terms.update(terms)
        
        # Update vocabulary
        index.vocabulary = {term: idx for idx, term in enumerate(sorted(all_terms))}
        
        # Calculate IDF scores
        index.idf_scores = self._calculate_idf_scores(documents, index.vocabulary)
        
        # Create TF-IDF vectors for all documents
        index.vectors = {}
        for record_id, terms in documents.items():
            index.vectors[record_id] = self._create_tfidf_vector(terms, index)
        
        import time
        index.last_updated = time.time()
    
    def _calculate_idf_scores(self, documents: Dict[str, List[str]], 
                            vocabulary: Dict[str, int]) -> Dict[str, float]:
        """Calculate IDF scores for all terms."""
        idf_scores = {}
        total_docs = len(documents)
        
        if total_docs == 0:
            return idf_scores
        
        # Count document frequency for each term
        doc_freq = defaultdict(int)
        for terms in documents.values():
            unique_terms = set(terms)
            for term in unique_terms:
                doc_freq[term] += 1
        
        # Calculate IDF scores
        for term in vocabulary:
            df = doc_freq.get(term, 0)
            if df > 0:
                idf_scores[term] = math.log(total_docs / df)
            else:
                idf_scores[term] = 0.0
        
        return idf_scores
    
    def _create_tfidf_vector(self, terms: List[str], index: VectorIndex) -> np.ndarray:
        """Create TF-IDF vector for a list of terms."""
        vector_size = len(index.vocabulary)
        if vector_size == 0:
            return np.array([])
        
        vector = np.zeros(vector_size)
        
        # Calculate term frequencies
        term_counts = Counter(terms)
        total_terms = len(terms)
        
        if total_terms == 0:
            return vector
        
        # Calculate TF-IDF for each term
        for term, count in term_counts.items():
            if term in index.vocabulary:
                term_idx = index.vocabulary[term]
                tf = count / total_terms
                idf = index.idf_scores.get(term, 0.0)
                vector[term_idx] = tf * idf
        
        return vector
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) == 0 or len(vec2) == 0:
            return 0.0
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector indexes."""
        stats = {}
        
        for memory_type, index in self.indexes.items():
            stats[memory_type] = {
                'document_count': len(index.vectors),
                'vocabulary_size': len(index.vocabulary),
                'last_updated': index.last_updated
            }
        
        return stats
    
    def clear_index(self, memory_type: Optional[str] = None) -> None:
        """Clear vector index for a memory type or all types."""
        if memory_type:
            if memory_type in self.indexes:
                del self.indexes[memory_type]
                logger.info(f"Cleared vector index for {memory_type}")
        else:
            self.indexes.clear()
            logger.info("Cleared all vector indexes")
    
    def shutdown(self) -> None:
        """Shutdown the vector search engine and clean up resources."""
        self.indexes.clear()
        logger.info("Vector search engine shutdown complete")


class VectorTextTransformer:
    """Text processing utilities for vector search."""
    
    def __init__(self):
        self._stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'the', 'this', 'but', 'they', 'have',
            'had', 'what', 'said', 'each', 'which', 'she', 'do', 'how', 'their'
        }
    
    def process_text(self, text: str) -> List[str]:
        """
        Process text for vector indexing.
        
        Args:
            text: Input text to process
            
        Returns:
            List[str]: Processed terms
        """
        if not text:
            return []
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters and split into words
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
        
        # Filter stop words and short words
        terms = [
            word for word in words 
            if word not in self._stop_words and len(word) >= 2
        ]
        
        return terms
    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract key terms from text.
        
        Args:
            text: Input text
            max_keywords: Maximum number of keywords to return
            
        Returns:
            List[str]: Key terms sorted by frequency
        """
        terms = self.process_text(text)
        
        if not terms:
            return []
        
        # Count term frequencies
        term_counts = Counter(terms)
        
        # Return most frequent terms
        return [term for term, count in term_counts.most_common(max_keywords)]