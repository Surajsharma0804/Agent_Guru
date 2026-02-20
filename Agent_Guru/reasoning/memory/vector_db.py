"""
Vector database for semantic memory search using ChromaDB.

This module provides persistent vector storage with semantic search capabilities
using ChromaDB. Memories are organized into collections by type (episodic,
semantic, preference, task) for efficient retrieval.

Performance Characteristics:
    - Time Complexity: O(log n) for search with HNSW index
    - Space Complexity: O(n*d) where n is memories, d is embedding dimension
    - Storage latency: <10ms per memory
    - Search latency: <100ms for top-k retrieval (k=5)

Design Principles:
    - Persistent storage with automatic backup
    - Separate collections per memory type
    - HNSW indexing for fast approximate search
    - Metadata filtering for user isolation
    - Automatic embedding generation

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import chromadb
from chromadb.config import Settings

from Agent_Guru.reasoning.models.memory import Memory, MemoryType

logger = logging.getLogger(__name__)


class VectorDatabase:
    """Vector database for semantic memory storage and retrieval.
    
    This class provides persistent vector storage using ChromaDB with separate
    collections for each memory type. It supports semantic search, metadata
    filtering, and automatic persistence.
    
    Collections:
        - episodic_memories: Episodic memories (events, experiences)
        - semantic_memories: Semantic memories (facts, knowledge)
        - preference_memories: Preference memories (user preferences)
        - task_memories: Task memories (task execution history)
    
    Attributes:
        db_path: Path to database storage directory
        client: ChromaDB client instance
        collections: Dictionary of collection name to collection object
    
    Example:
        >>> db = VectorDatabase(db_path="./memory_db")
        >>> # Store a memory
        >>> memory_id = db.store(
        ...     memory_type=MemoryType.EPISODIC,
        ...     content="User set a timer",
        ...     embedding=[0.1, 0.2, ...],  # 384-dim
        ...     metadata={"user_id": "user_123", "action": "set_timer"}
        ... )
        >>> # Search for similar memories
        >>> results = db.search(
        ...     memory_type=MemoryType.EPISODIC,
        ...     query_embedding=[0.1, 0.2, ...],
        ...     user_id="user_123",
        ...     top_k=5
        ... )
    """
    
    # Collection names for each memory type
    COLLECTION_NAMES = {
        MemoryType.EPISODIC: "episodic_memories",
        MemoryType.SEMANTIC: "semantic_memories",
        MemoryType.PREFERENCE: "preference_memories",
        MemoryType.TASK: "task_memories",
    }
    
    def __init__(
        self,
        db_path: str = "./memory_db",
        embedding_dimension: int = 384,
        in_memory: bool = False
    ):
        """Initialize vector database.
        
        Args:
            db_path: Path to database storage directory
            embedding_dimension: Dimension of embedding vectors (default 384)
            in_memory: Use in-memory database (for testing, default False)
        
        Raises:
            RuntimeError: If database initialization fails
        """
        self.db_path = Path(db_path)
        self.embedding_dimension = embedding_dimension
        self.in_memory = in_memory
        
        logger.info(f"Initializing VectorDatabase at {self.db_path} (in_memory={in_memory})")
        
        # Create database directory if not in-memory mode
        if not in_memory:
            self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        try:
            if in_memory:
                # Use in-memory client for testing (no file locking issues)
                self.client = chromadb.Client(
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                logger.info("ChromaDB in-memory client initialized successfully")
            else:
                # Use persistent client for production
                self.client = chromadb.PersistentClient(
                    path=str(self.db_path),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                logger.info("ChromaDB persistent client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise RuntimeError(f"Database initialization failed: {e}") from e
        
        # Initialize collections for each memory type
        self.collections: Dict[MemoryType, Any] = {}
        self._initialize_collections()
    
    def _initialize_collections(self) -> None:
        """Initialize collections for each memory type.
        
        Creates or retrieves collections with HNSW indexing for fast search.
        Each collection stores memories of a specific type.
        
        Raises:
            RuntimeError: If collection initialization fails
        """
        for memory_type, collection_name in self.COLLECTION_NAMES.items():
            try:
                # Get or create collection with HNSW index
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={
                        "hnsw:space": "cosine",  # Cosine similarity
                        "hnsw:construction_ef": 200,  # Build quality
                        "hnsw:search_ef": 100,  # Search quality
                        "hnsw:M": 16,  # Connections per node
                    }
                )
                self.collections[memory_type] = collection
                
                # Log collection stats
                count = collection.count()
                logger.info(
                    f"Initialized collection '{collection_name}' "
                    f"with {count} memories"
                )
            
            except Exception as e:
                logger.error(
                    f"Failed to initialize collection '{collection_name}': {e}"
                )
                raise RuntimeError(
                    f"Collection initialization failed: {e}"
                ) from e
    
    def store(
        self,
        memory_type: MemoryType,
        memory_id: UUID,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """Store a memory in the vector database.
        
        Time Complexity: O(log n) for HNSW insertion
        Space Complexity: O(d) where d is embedding dimension
        
        Args:
            memory_type: Type of memory to store
            memory_id: Unique identifier for the memory
            content: Text content of the memory
            embedding: Embedding vector (384-dim)
            metadata: Additional metadata (must include user_id)
        
        Returns:
            Memory ID as string
        
        Raises:
            ValueError: If embedding dimension is incorrect or user_id missing
            RuntimeError: If storage fails
        
        Example:
            >>> db = VectorDatabase()
            >>> memory_id = db.store(
            ...     memory_type=MemoryType.EPISODIC,
            ...     memory_id=UUID("..."),
            ...     content="User set a timer",
            ...     embedding=[0.1, 0.2, ...],
            ...     metadata={"user_id": "user_123"}
            ... )
        """
        # Validate embedding dimension
        if len(embedding) != self.embedding_dimension:
            raise ValueError(
                f"Embedding must be {self.embedding_dimension}-dimensional, "
                f"got {len(embedding)}"
            )
        
        # Validate user_id in metadata
        if "user_id" not in metadata:
            raise ValueError("metadata must include 'user_id'")
        
        # Get collection for this memory type
        collection = self.collections.get(memory_type)
        if collection is None:
            raise ValueError(f"Invalid memory type: {memory_type}")
        
        # Convert UUID to string for ChromaDB
        memory_id_str = str(memory_id)
        
        try:
            # Store in ChromaDB
            collection.add(
                ids=[memory_id_str],
                embeddings=[embedding],
                documents=[content],
                metadatas=[metadata]
            )
            
            logger.debug(
                f"Stored memory {memory_id_str} in {memory_type.value} collection"
            )
            
            return memory_id_str
        
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            raise RuntimeError(f"Memory storage failed: {e}") from e
    
    def search(
        self,
        memory_type: MemoryType,
        query_embedding: List[float],
        user_id: str,
        top_k: int = 5,
        min_similarity: float = 0.0
    ) -> List[Tuple[str, str, float, Dict[str, Any]]]:
        """Search for similar memories using semantic search.
        
        Time Complexity: O(log n) for HNSW search
        Space Complexity: O(k) for results
        
        Args:
            memory_type: Type of memories to search
            query_embedding: Query embedding vector (384-dim)
            user_id: User ID to filter results (privacy)
            top_k: Number of results to return (default 5)
            min_similarity: Minimum similarity threshold (default 0.0)
        
        Returns:
            List of (memory_id, content, similarity, metadata) tuples
            sorted by similarity (highest first)
        
        Raises:
            ValueError: If embedding dimension is incorrect
            RuntimeError: If search fails
        
        Example:
            >>> db = VectorDatabase()
            >>> results = db.search(
            ...     memory_type=MemoryType.EPISODIC,
            ...     query_embedding=[0.1, 0.2, ...],
            ...     user_id="user_123",
            ...     top_k=5
            ... )
            >>> for memory_id, content, similarity, metadata in results:
            ...     print(f"{content}: {similarity:.3f}")
        """
        # Validate embedding dimension
        if len(query_embedding) != self.embedding_dimension:
            raise ValueError(
                f"Query embedding must be {self.embedding_dimension}-dimensional, "
                f"got {len(query_embedding)}"
            )
        
        # Get collection for this memory type
        collection = self.collections.get(memory_type)
        if collection is None:
            raise ValueError(f"Invalid memory type: {memory_type}")
        
        try:
            # Search with user_id filter for privacy
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where={"user_id": user_id},  # Filter by user
                include=["documents", "metadatas", "distances"]
            )
            
            # Extract and format results
            formatted_results = []
            
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    memory_id = results["ids"][0][i]
                    content = results["documents"][0][i]
                    distance = results["distances"][0][i]
                    metadata = results["metadatas"][0][i]
                    
                    # Convert distance to similarity (cosine distance to similarity)
                    # ChromaDB returns cosine distance (0 = identical, 2 = opposite)
                    similarity = 1.0 - (distance / 2.0)
                    
                    # Filter by minimum similarity
                    if similarity >= min_similarity:
                        formatted_results.append(
                            (memory_id, content, similarity, metadata)
                        )
            
            logger.debug(
                f"Found {len(formatted_results)} memories for user {user_id} "
                f"in {memory_type.value} collection"
            )
            
            return formatted_results
        
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            raise RuntimeError(f"Memory search failed: {e}") from e
    
    def get(
        self,
        memory_type: MemoryType,
        memory_id: UUID
    ) -> Optional[Tuple[str, List[float], Dict[str, Any]]]:
        """Retrieve a specific memory by ID.
        
        Time Complexity: O(1) for direct lookup
        Space Complexity: O(d) where d is embedding dimension
        
        Args:
            memory_type: Type of memory to retrieve
            memory_id: Unique identifier of the memory
        
        Returns:
            Tuple of (content, embedding, metadata) or None if not found
        
        Raises:
            RuntimeError: If retrieval fails
        
        Example:
            >>> db = VectorDatabase()
            >>> result = db.get(
            ...     memory_type=MemoryType.EPISODIC,
            ...     memory_id=UUID("...")
            ... )
            >>> if result:
            ...     content, embedding, metadata = result
        """
        # Get collection for this memory type
        collection = self.collections.get(memory_type)
        if collection is None:
            raise ValueError(f"Invalid memory type: {memory_type}")
        
        memory_id_str = str(memory_id)
        
        try:
            # Get memory by ID
            results = collection.get(
                ids=[memory_id_str],
                include=["documents", "embeddings", "metadatas"]
            )
            
            # Check if memory exists
            if not results["ids"] or not results["ids"]:
                return None
            
            content = results["documents"][0]
            embedding = results["embeddings"][0]
            metadata = results["metadatas"][0]
            
            return (content, embedding, metadata)
        
        except Exception as e:
            logger.error(f"Failed to retrieve memory: {e}")
            raise RuntimeError(f"Memory retrieval failed: {e}") from e
    
    def update_metadata(
        self,
        memory_type: MemoryType,
        memory_id: UUID,
        metadata: Dict[str, Any]
    ) -> None:
        """Update metadata for a memory (e.g., relevance score).
        
        Time Complexity: O(1) for metadata update
        Space Complexity: O(1)
        
        Args:
            memory_type: Type of memory to update
            memory_id: Unique identifier of the memory
            metadata: New metadata to set
        
        Raises:
            RuntimeError: If update fails
        
        Example:
            >>> db = VectorDatabase()
            >>> db.update_metadata(
            ...     memory_type=MemoryType.EPISODIC,
            ...     memory_id=UUID("..."),
            ...     metadata={"relevance_score": 0.9, "user_id": "user_123"}
            ... )
        """
        # Get collection for this memory type
        collection = self.collections.get(memory_type)
        if collection is None:
            raise ValueError(f"Invalid memory type: {memory_type}")
        
        memory_id_str = str(memory_id)
        
        try:
            # Update metadata
            collection.update(
                ids=[memory_id_str],
                metadatas=[metadata]
            )
            
            logger.debug(f"Updated metadata for memory {memory_id_str}")
        
        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")
            raise RuntimeError(f"Metadata update failed: {e}") from e
    
    def delete(
        self,
        memory_type: MemoryType,
        memory_id: UUID
    ) -> None:
        """Delete a memory from the database.
        
        Time Complexity: O(log n) for HNSW deletion
        Space Complexity: O(1)
        
        Args:
            memory_type: Type of memory to delete
            memory_id: Unique identifier of the memory
        
        Raises:
            RuntimeError: If deletion fails
        
        Example:
            >>> db = VectorDatabase()
            >>> db.delete(
            ...     memory_type=MemoryType.EPISODIC,
            ...     memory_id=UUID("...")
            ... )
        """
        # Get collection for this memory type
        collection = self.collections.get(memory_type)
        if collection is None:
            raise ValueError(f"Invalid memory type: {memory_type}")
        
        memory_id_str = str(memory_id)
        
        try:
            # Delete memory
            collection.delete(ids=[memory_id_str])
            
            logger.debug(f"Deleted memory {memory_id_str}")
        
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            raise RuntimeError(f"Memory deletion failed: {e}") from e
    
    def count(self, memory_type: MemoryType) -> int:
        """Get the number of memories in a collection.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            memory_type: Type of memories to count
        
        Returns:
            Number of memories in the collection
        
        Example:
            >>> db = VectorDatabase()
            >>> count = db.count(MemoryType.EPISODIC)
            >>> print(f"Episodic memories: {count}")
        """
        collection = self.collections.get(memory_type)
        if collection is None:
            raise ValueError(f"Invalid memory type: {memory_type}")
        
        return collection.count()
    
    def reset(self, memory_type: Optional[MemoryType] = None) -> None:
        """Reset database (delete all memories).
        
        WARNING: This is destructive and cannot be undone!
        
        Args:
            memory_type: Type of memories to reset, or None for all types
        
        Example:
            >>> db = VectorDatabase()
            >>> # Reset specific collection
            >>> db.reset(MemoryType.EPISODIC)
            >>> # Reset all collections
            >>> db.reset()
        """
        if memory_type is None:
            # Reset all collections
            for mt in MemoryType:
                collection_name = self.COLLECTION_NAMES[mt]
                try:
                    self.client.delete_collection(name=collection_name)
                    logger.info(f"Deleted collection '{collection_name}'")
                except Exception as e:
                    logger.warning(
                        f"Failed to delete collection '{collection_name}': {e}"
                    )
            
            # Reinitialize collections
            self._initialize_collections()
        else:
            # Reset specific collection
            collection_name = self.COLLECTION_NAMES[memory_type]
            try:
                self.client.delete_collection(name=collection_name)
                logger.info(f"Deleted collection '{collection_name}'")
                
                # Recreate collection
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={
                        "hnsw:space": "cosine",
                        "hnsw:construction_ef": 200,
                        "hnsw:search_ef": 100,
                        "hnsw:M": 16,
                    }
                )
                self.collections[memory_type] = collection
            except Exception as e:
                logger.error(
                    f"Failed to reset collection '{collection_name}': {e}"
                )
                raise RuntimeError(f"Collection reset failed: {e}") from e
