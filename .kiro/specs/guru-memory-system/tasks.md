# Implementation Plan: Guru Memory System

## Overview

This implementation plan breaks down the Guru Memory System into incremental, testable components. The approach follows a bottom-up strategy: build core infrastructure (encryption, storage layers) first, then compose them into higher-level APIs. Each task includes property-based tests to validate correctness properties from the design document.

The implementation uses Python with the following key dependencies:
- `cryptography` for encryption (AES-256-GCM, HKDF)
- `networkx` for graph operations with `sqlite3` for persistence
- `chromadb` for vector storage and similarity search
- `sentence-transformers` for semantic embeddings
- `hypothesis` for property-based testing
- `pytest` for unit and integration testing

## Tasks

- [ ] 1. Set up project structure and dependencies
  - Create directory structure: `guru_memory/` with subdirectories for core components
  - Create `pyproject.toml` with dependencies (cryptography, networkx, chromadb, sentence-transformers, hypothesis, pytest)
  - Create `__init__.py` files for package structure
  - Set up pytest configuration with coverage tracking
  - _Requirements: All (foundation)_

- [ ] 2. Implement encryption layer
  - [ ] 2.1 Create `encryption.py` with `EncryptionLayer` class
    - Implement `__init__` with master key validation (32 bytes)
    - Implement `derive_key` using HKDF with SHA-256
    - Implement `encrypt` using AES-256-GCM (returns nonce + ciphertext + tag)
    - Implement `decrypt` with error handling for invalid ciphertext
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ]* 2.2 Write property test for encryption round-trip
    - **Property 4: Encryption Round-Trip Preservation**
    - **Validates: Requirements 3.2**
  
  - [ ]* 2.3 Write property test for key derivation determinism
    - **Property 5: Key Derivation Determinism**
    - **Validates: Requirements 3.3**
  
  - [ ]* 2.4 Write unit tests for encryption edge cases
    - Test invalid master key length
    - Test decryption with wrong key
    - Test decryption with corrupted ciphertext
    - _Requirements: 3.4_

- [ ] 3. Implement embedding model wrapper
  - [ ] 3.1 Create `embedding_model.py` with `EmbeddingModel` class
    - Implement `__init__` to load sentence-transformers model
    - Implement `encode` for single text or list of texts
    - Implement `encode_batch` with configurable batch size
    - Cache model instance to avoid reloading
    - _Requirements: 2.1_
  
  - [ ]* 3.2 Write unit tests for embedding model
    - Test single text encoding
    - Test batch encoding
    - Test embedding dimension consistency
    - _Requirements: 2.1_

- [ ] 4. Implement graph store with SQLite persistence
  - [ ] 4.1 Create `graph_store.py` with `GraphStore` class
    - Implement `__init__` with NetworkX DiGraph and SQLite connection
    - Create SQLite schema (nodes and edges tables with indexes)
    - Implement `add_node` with encrypted content storage
    - Implement `add_edge` for temporal relationships
    - Implement `get_node` with content decryption
    - _Requirements: 1.1, 1.2, 6.2_
  
  - [ ] 4.2 Implement graph query operations
    - Implement `query_by_time_range` with timestamp filtering
    - Implement `traverse_from_node` using NetworkX traversal
    - Implement `remove_node` with edge cleanup
    - Implement `get_node_importance` using PageRank and degree centrality
    - _Requirements: 1.3, 4.2, 4.5_
  
  - [ ] 4.3 Implement persistence operations
    - Implement `persist` to save graph to SQLite
    - Implement `load` to restore graph from SQLite
    - Use transactions for atomic operations
    - _Requirements: 6.1, 6.2, 6.5_
  
  - [ ]* 4.4 Write property test for temporal graph traversal
    - **Property 2: Temporal Graph Traversal Completeness**
    - **Validates: Requirements 1.2, 1.3**
  
  - [ ]* 4.5 Write property test for no plaintext on disk
    - **Property 6: No Plaintext on Disk**
    - **Validates: Requirements 3.5**
  
  - [ ]* 4.6 Write property test for pruning removes orphaned edges
    - **Property 8: Pruning Removes Orphaned Edges**
    - **Validates: Requirements 4.5**
  
  - [ ]* 4.7 Write unit tests for graph store
    - Test node and edge operations
    - Test time range queries
    - Test persistence and loading
    - Test error handling for invalid operations
    - _Requirements: 1.1, 1.2, 1.3, 6.1_

- [ ] 5. Checkpoint - Ensure core storage tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement vector store with ChromaDB
  - [ ] 6.1 Create `vector_store.py` with `VectorStore` class
    - Implement `__init__` with ChromaDB client and collection setup
    - Implement `add_memory` to store embedding with metadata
    - Implement `query` for similarity search with metadata filtering
    - Implement `update_metadata` for metadata updates
    - Implement `delete` to remove memory from collection
    - Implement `get_collection_size` for capacity tracking
    - _Requirements: 2.2, 2.3, 2.4, 9.2_
  
  - [ ]* 6.2 Write property test for semantic query result ordering
    - **Property 3: Semantic Query Result Ordering**
    - **Validates: Requirements 2.2, 2.3, 2.4**
  
  - [ ]* 6.3 Write property test for metadata filtering correctness
    - **Property 19: Metadata Filtering Correctness**
    - **Validates: Requirements 9.2**
  
  - [ ]* 6.4 Write unit tests for vector store
    - Test embedding storage and retrieval
    - Test similarity search with various thresholds
    - Test metadata filtering
    - Test collection management
    - _Requirements: 2.2, 2.3, 2.4, 9.2_

- [ ] 7. Implement data models
  - [ ] 7.1 Create `models.py` with `Memory` dataclass
    - Define `Memory` dataclass with all fields (id, content, timestamp, metadata, embedding, importance)
    - Implement `to_dict` for JSON serialization
    - Implement `from_dict` for JSON deserialization with validation
    - Implement `__eq__` for equality comparison
    - _Requirements: 7.1, 7.2_
  
  - [ ]* 7.2 Write property test for serialization round-trip
    - **Property 14: Serialization Round-Trip Preservation**
    - **Validates: Requirements 7.1, 7.5**
  
  - [ ]* 7.3 Write unit tests for data models
    - Test serialization to JSON
    - Test deserialization with validation
    - Test invalid schema handling
    - _Requirements: 7.1, 7.2_

- [ ] 8. Implement query engine with caching
  - [ ] 8.1 Create `query_engine.py` with `QueryEngine` class
    - Implement `__init__` with store references and LRU cache
    - Implement `semantic_query` with caching and embedding generation
    - Implement `temporal_query` with graph traversal
    - Implement `hybrid_query` combining semantic and temporal constraints
    - Implement `_cache_get` and `_cache_put` for LRU cache management
    - _Requirements: 2.2, 1.3, 5.3_
  
  - [ ]* 8.2 Write property test for cache consistency
    - **Property 9: Cache Consistency**
    - **Validates: Requirements 5.3**
  
  - [ ]* 8.3 Write property test for batch query correctness
    - **Property 10: Batch Query Correctness**
    - **Validates: Requirements 5.5**
  
  - [ ]* 8.4 Write unit tests for query engine
    - Test semantic queries with various parameters
    - Test temporal queries with time ranges
    - Test hybrid queries
    - Test cache hit/miss behavior
    - _Requirements: 2.2, 1.3, 5.3, 5.5_

- [ ] 9. Implement pruning manager
  - [ ] 9.1 Create `pruning.py` with `PruningManager` class
    - Implement `__init__` with store references
    - Implement `calculate_importance` using recency, access frequency, and centrality
    - Implement `prune_by_importance` to remove low-importance memories
    - Implement `prune_by_age` to remove old memories
    - Implement `prune_by_capacity` to enforce size limits
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [ ]* 9.2 Write property test for pruning preserves important memories
    - **Property 7: Pruning Preserves Important Memories**
    - **Validates: Requirements 4.2, 4.3**
  
  - [ ]* 9.3 Write unit tests for pruning strategies
    - Test importance-based pruning
    - Test age-based pruning
    - Test capacity-based pruning
    - Test automatic trigger on threshold
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 10. Checkpoint - Ensure component tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement main Memory API
  - [ ] 11.1 Create `memory_api.py` with `MemorySystem` class
    - Implement `__init__` to initialize all components (encryption, stores, query engine, pruning)
    - Implement `store_memory` with atomic dual-store persistence
    - Implement `query_similar` delegating to query engine
    - Implement `query_temporal` delegating to query engine
    - Implement `update_metadata` with immutability checks
    - Implement `delete_memory` with cleanup
    - _Requirements: 1.1, 2.2, 1.3, 6.2, 9.4_
  
  - [ ] 11.2 Implement backup and import operations
    - Implement `export_memories` to JSON file
    - Implement `import_memories` from JSON file with duplicate prevention
    - Implement `prune` delegating to pruning manager
    - Implement `close` for graceful shutdown with flush
    - _Requirements: 7.3, 7.4, 4.1, 6.5_
  
  - [ ]* 11.3 Write property test for memory creation completeness
    - **Property 1: Memory Creation Completeness**
    - **Validates: Requirements 1.1, 1.4, 2.1**
  
  - [ ]* 11.4 Write property test for atomic dual-store persistence
    - **Property 12: Atomic Dual-Store Persistence**
    - **Validates: Requirements 6.2**
  
  - [ ]* 11.5 Write property test for persistence across sessions
    - **Property 11: Persistence Across Sessions**
    - **Validates: Requirements 6.1, 6.5**
  
  - [ ]* 11.6 Write property test for metadata preservation
    - **Property 18: Metadata Preservation**
    - **Validates: Requirements 9.1, 9.5**
  
  - [ ]* 11.7 Write property test for metadata update immutability
    - **Property 20: Metadata Update Immutability**
    - **Validates: Requirements 9.4**
  
  - [ ]* 11.8 Write property test for backup completeness
    - **Property 13: Backup Completeness**
    - **Validates: Requirements 6.4, 7.3**
  
  - [ ]* 11.9 Write property test for import duplicate prevention
    - **Property 15: Import Duplicate Prevention**
    - **Validates: Requirements 7.4**

- [ ] 12. Implement error handling and degraded mode
  - [ ] 12.1 Create exception hierarchy in `exceptions.py`
    - Define `MemorySystemError` base exception
    - Define specific exceptions (EncryptionError, StorageError, ValidationError, QueryError, DegradedModeError)
    - _Requirements: 10.1, 10.2_
  
  - [ ] 12.2 Add retry logic and degraded mode to MemorySystem
    - Implement connection retry with exponential backoff
    - Implement degraded mode state management
    - Implement write queue for degraded mode
    - Implement automatic recovery and flush
    - Add comprehensive error logging
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [ ]* 12.3 Write property test for degraded mode write queueing
    - **Property 21: Degraded Mode Write Queueing**
    - **Validates: Requirements 10.3, 10.4**
  
  - [ ]* 12.4 Write property test for error logging completeness
    - **Property 22: Error Logging Completeness**
    - **Validates: Requirements 10.5**
  
  - [ ]* 12.5 Write unit tests for error handling
    - Test connection failure and retry
    - Test degraded mode transitions
    - Test write queue management
    - Test recovery and flush
    - Test error logging
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 13. Implement concurrent access safety
  - [ ] 13.1 Add thread safety to MemorySystem
    - Add locks for critical sections (store operations, cache access)
    - Implement connection pooling for database access
    - Add transaction isolation for multi-memory operations
    - Add deadlock detection and retry logic
    - _Requirements: 8.1, 8.2, 8.4, 8.5_
  
  - [ ]* 13.2 Write property test for concurrent access safety
    - **Property 16: Concurrent Access Safety**
    - **Validates: Requirements 8.1, 8.2**
  
  - [ ]* 13.3 Write property test for transaction isolation
    - **Property 17: Transaction Isolation**
    - **Validates: Requirements 8.5**
  
  - [ ]* 13.4 Write unit tests for concurrent access
    - Test concurrent reads and writes
    - Test deadlock handling
    - Test transaction isolation
    - _Requirements: 8.1, 8.2, 8.4, 8.5_

- [ ] 14. Checkpoint - Ensure all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Integration testing and optimization
  - [ ]* 15.1 Write integration tests for end-to-end workflows
    - Test complete memory lifecycle (store, query, update, delete)
    - Test backup and restore workflow
    - Test system restart and persistence
    - Test concurrent access from multiple threads
    - _Requirements: All_
  
  - [ ]* 15.2 Add performance benchmarks
    - Benchmark memory storage latency (target: <10ms)
    - Benchmark semantic query latency (target: <100ms for 100k memories)
    - Benchmark graph traversal latency (target: <50ms for depth 5)
    - Benchmark encryption/decryption throughput
    - Benchmark pruning operation duration
    - _Requirements: 2.5, 5.4_
  
  - [ ] 15.3 Create example usage scripts
    - Create `examples/basic_usage.py` demonstrating core operations
    - Create `examples/advanced_queries.py` demonstrating complex queries
    - Create `examples/backup_restore.py` demonstrating backup workflow
    - Add docstrings and comments for clarity

- [ ] 16. Code quality and documentation
  - [ ] 16.1 Run code quality tools
    - Format code with `black`
    - Lint with `flake8` (zero errors)
    - Type check with `mypy` in strict mode
    - Check with `pylint` (score ≥ 9.0/10)
  
  - [ ] 16.2 Add comprehensive docstrings
    - Add module-level docstrings to all files
    - Add class-level docstrings with usage examples
    - Add method-level docstrings with parameter descriptions
    - Use Google-style docstring format
  
  - [ ] 16.3 Create README.md for the memory system
    - Document installation instructions
    - Document basic usage examples
    - Document configuration options
    - Document performance characteristics
    - Document security considerations

- [ ] 17. Final checkpoint and commit
  - Run full test suite with coverage report (target: 90%+)
  - Verify all property tests pass (100 iterations each)
  - Verify all integration tests pass
  - Verify all benchmarks meet targets
  - Git commit with message: "feat: implement guru-memory-system with property-based testing"
  - Git push to remote repository

## Notes

- Tasks marked with `*` are optional test tasks that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end workflows
- Checkpoints ensure incremental validation throughout implementation
- All code must pass linting and type checking before final commit
- Performance benchmarks ensure the system meets latency targets
