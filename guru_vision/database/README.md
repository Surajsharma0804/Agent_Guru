# Face Database Module

This module provides data structures and database management for the GuruVision facial recognition system.

## Overview

The face database module handles storage, retrieval, and matching of face embeddings with associated identity information. It supports:

- In-memory storage with disk persistence
- Multi-embedding storage per identity (different angles, lighting conditions)
- Cosine similarity-based identity matching
- CRUD operations (Create, Read, Update, Delete)
- JSON export/import for backup and transfer
- Permission-based access control

## Components

### Data Classes

#### `Embedding`
Represents a single face embedding with metadata.

**Attributes:**
- `vector`: 512-dimensional numpy array (float32)
- `timestamp`: ISO format timestamp
- `angle_category`: Face angle (frontal, profile, 45_degree)
- `lighting_condition`: Lighting (normal, low_light, bright)
- `metadata`: Additional custom metadata

#### `Identity`
Represents a person's identity with multiple embeddings.

**Attributes:**
- `name`: Unique identifier
- `embeddings`: List of Embedding objects
- `permission_level`: Access level (admin, user, guest, denied)
- `date_added`: ISO format timestamp
- `metadata`: Additional custom metadata

### FaceDatabase Class

Main database class providing all storage and retrieval operations.

#### Initialization
```python
from guru_vision.database import FaceDatabase

db = FaceDatabase("guru_face/database/identities.json")
```

#### Adding Identities
```python
import numpy as np

# Create embeddings (normally from recognition model)
embeddings = [np.random.randn(512).astype(np.float32) for _ in range(3)]

# Add identity
db.add_identity("John Doe", embeddings, permission_level="user")
```

#### Adding Embeddings to Existing Identity
```python
new_embedding = np.random.randn(512).astype(np.float32)
db.add_embedding(
    "John Doe", 
    new_embedding,
    angle_category="profile",
    lighting_condition="low_light"
)
```

#### Searching for Matches
```python
query_embedding = np.random.randn(512).astype(np.float32)
result = db.search(query_embedding, threshold=0.6)

if result:
    print(f"Match: {result['identity']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Permission: {result['permission_level']}")
```

#### Retrieving Identities
```python
# Get specific identity
identity = db.get_identity("John Doe")

# Get all identities
all_identities = db.get_all_identities()
```

#### Updating Permissions
```python
db.update_permission("John Doe", "admin")
```

#### Removing Identities
```python
db.remove_identity("John Doe")
```

#### Persistence
```python
# Save to disk
db.save()

# Load from disk
db.load()
```

#### Export/Import
```python
# Export to backup
db.export_json("backup.json")

# Import from backup (replace existing)
db.import_json("backup.json", merge=False)

# Import and merge with existing
db.import_json("backup.json", merge=True)
```

## Storage Format

The database is stored as JSON with base64-encoded embeddings:

```json
{
  "version": "1.0",
  "identities": [
    {
      "name": "John Doe",
      "permission_level": "admin",
      "date_added": "2024-01-15T10:30:00Z",
      "metadata": {},
      "embeddings": [
        {
          "vector": "base64_encoded_512_float32_array",
          "timestamp": "2024-01-15T10:30:00Z",
          "angle_category": "frontal",
          "lighting_condition": "normal",
          "metadata": {}
        }
      ]
    }
  ]
}
```

## Identity Matching

The database uses cosine similarity to match query embeddings against stored embeddings:

1. For each identity, compare the query against all stored embeddings
2. Find the maximum similarity score across all identities
3. If the score exceeds the threshold, return the matched identity
4. Otherwise, return None (no match)

**Cosine Similarity Formula:**
```
similarity = (vec1 · vec2) / (||vec1|| * ||vec2||)
```

Result is clamped to [0.0, 1.0] range.

## Permission Levels

Four standard permission levels are supported:

- `admin`: Full system access
- `user`: Standard access
- `guest`: Limited access
- `denied`: Access rejected

Custom permission attributes can be stored in the metadata field.

## Requirements Satisfied

This implementation satisfies the following requirements from the spec:

- **Requirement 6.1-6.6**: Multi-angle identity memory with metadata
- **Requirement 9.1**: Permission level storage and retrieval
- **Requirement 12.1-12.7**: Complete database CRUD operations
- **Requirement 5.2-5.7**: Cosine similarity-based identity matching

## Testing

Run the test suite:
```bash
python -m pytest guru_vision/database/test_face_db.py -v
```

Run the example:
```bash
python -m guru_vision.database.example_usage
```

## Performance Considerations

- All identities are loaded into memory at startup for fast lookups
- Search complexity: O(N * M) where N = number of identities, M = average embeddings per identity
- For large databases (>10,000 identities), consider using approximate nearest neighbor search (e.g., FAISS)
- Database saves are synchronous - consider async saves for high-frequency updates

## Future Enhancements

Potential improvements for future versions:

1. **Approximate Nearest Neighbor**: Use FAISS or Annoy for faster search in large databases
2. **Database Sharding**: Split database across multiple files for better scalability
3. **Incremental Saves**: Only save modified identities instead of entire database
4. **Compression**: Compress embeddings for smaller file sizes
5. **Encryption**: Encrypt embeddings at rest for sensitive applications
6. **Versioning**: Track embedding versions for model updates
7. **Batch Operations**: Add batch insert/update/delete methods
8. **Query Optimization**: Cache frequently accessed identities
