# Identity Management API

This document describes the identity management methods in the GuruVision Engine, which allow you to add, remove, query, and update identities without retraining the model.

## Overview

The GuruVision Engine provides four main identity management methods:

1. **add_identity()** - Add new identities with face images
2. **remove_identity()** - Remove identities from the database
3. **get_identities()** - Query all stored identities
4. **update_permission()** - Update permission levels

These methods enable incremental identity addition, which is a key feature for production deployments where retraining the entire model for each new person would be impractical.

## Requirements Implemented

- **16.1**: Add new identities without retraining the model
- **16.2**: Store embeddings immediately in the database
- **16.3**: Recognize newly added identities in subsequent operations
- **16.4**: Require at least 5 images for reliable recognition
- **16.5**: Support batch import and individual addition
- **12.2**: Update existing identity information including permission level
- **12.3**: Delete identities and all associated embeddings
- **12.4**: Query all stored identities with their metadata
- **9.5**: Allow administrators to modify permission level assignments

## API Reference

### add_identity()

Add a new identity without retraining the model.

```python
def add_identity(
    self,
    name: str,
    images: List[np.ndarray],
    permission_level: str = "user"
) -> bool
```

**Parameters:**
- `name` (str): Unique identifier for the identity
- `images` (List[np.ndarray]): List of face images in BGR format (OpenCV format)
- `permission_level` (str): Permission level - one of: "admin", "user", "guest", "denied"

**Returns:**
- `bool`: True if identity was added successfully, False otherwise

**Raises:**
- `RuntimeError`: If engine is not initialized
- `ValueError`: If inputs are invalid

**Process:**
1. Validates inputs (name, images, permission level)
2. For each image:
   - Detects face using RetinaFace
   - Aligns face using landmark-based alignment
   - Extracts 512-dimensional embedding using ONNX model
3. Stores all embeddings in the database
4. Saves database to disk
5. Emits "new_identity" event

**Example:**
```python
import cv2
from guru_vision.engine import GuruVisionEngine

# Initialize engine
engine = GuruVisionEngine()
engine.initialize()

# Load face images
images = [
    cv2.imread("person1_front.jpg"),
    cv2.imread("person1_left.jpg"),
    cv2.imread("person1_right.jpg"),
    cv2.imread("person1_smile.jpg"),
    cv2.imread("person1_neutral.jpg"),
]

# Add identity
success = engine.add_identity(
    name="John Doe",
    images=images,
    permission_level="user"
)

if success:
    print("Identity added successfully!")
```

**Notes:**
- Minimum 5 images recommended for reliable recognition (Requirement 16.4)
- Images should include different angles, lighting conditions, and expressions
- If fewer than 5 images provided, a warning is logged but identity is still added
- Images with no detectable face are skipped with a warning
- Images with multiple faces use the face with highest confidence

---

### remove_identity()

Remove an identity and all associated embeddings from the database.

```python
def remove_identity(self, name: str) -> bool
```

**Parameters:**
- `name` (str): Identity name to remove

**Returns:**
- `bool`: True if identity was removed, False if not found

**Raises:**
- `RuntimeError`: If engine is not initialized
- `ValueError`: If name is invalid

**Process:**
1. Validates input
2. Calls database.remove_identity()
3. Saves database to disk
4. Emits "identity_removed" event

**Example:**
```python
# Remove an identity
success = engine.remove_identity("John Doe")

if success:
    print("Identity removed successfully!")
else:
    print("Identity not found")
```

---

### get_identities()

Get information about all stored identities.

```python
def get_identities(self) -> List[IdentityInfo]
```

**Returns:**
- `List[IdentityInfo]`: List of IdentityInfo objects

**Raises:**
- `RuntimeError`: If engine is not initialized

**IdentityInfo Structure:**
```python
@dataclass
class IdentityInfo:
    name: str                    # Identity name
    permission_level: str        # Permission level
    num_embeddings: int          # Number of stored embeddings
    date_added: str             # ISO format timestamp
    metadata: Dict[str, Any]    # Additional metadata
```

**Example:**
```python
# Get all identities
identities = engine.get_identities()

print(f"Total identities: {len(identities)}")

for identity in identities:
    print(f"Name: {identity.name}")
    print(f"  Permission: {identity.permission_level}")
    print(f"  Embeddings: {identity.num_embeddings}")
    print(f"  Added: {identity.date_added}")
```

---

### update_permission()

Update the permission level for an identity.

```python
def update_permission(self, name: str, permission_level: str) -> bool
```

**Parameters:**
- `name` (str): Identity name
- `permission_level` (str): New permission level - one of: "admin", "user", "guest", "denied"

**Returns:**
- `bool`: True if updated successfully, False if identity not found

**Raises:**
- `RuntimeError`: If engine is not initialized
- `ValueError`: If permission_level is invalid

**Process:**
1. Validates inputs
2. Calls database.update_permission()
3. Saves database to disk
4. Emits "permission_changed" event

**Example:**
```python
# Promote user to admin
success = engine.update_permission("John Doe", "admin")

if success:
    print("Permission updated successfully!")
else:
    print("Identity not found")
```

---

## Permission Levels

The system supports four permission levels:

1. **admin**: Full system access
2. **user**: Standard access
3. **guest**: Limited access
4. **denied**: Access denied (logged as security event)

Permission levels are used by the AI agent to enforce access control policies based on who is recognized.

---

## Best Practices

### Image Collection

For best recognition accuracy:

1. **Quantity**: Provide 5-10 images per identity (Requirement 16.4)
2. **Variety**: Include different:
   - Angles (frontal, 45°, profile)
   - Lighting conditions (normal, low-light, bright)
   - Expressions (neutral, smiling, serious)
3. **Quality**: Use clear, well-lit images with visible faces
4. **Single Face**: Each image should contain only one face (or the target face should be largest)

### Error Handling

Always check return values and handle errors:

```python
try:
    success = engine.add_identity(name, images, permission_level)
    if not success:
        print("Failed to add identity - check logs for details")
except RuntimeError as e:
    print(f"Engine not initialized: {e}")
except ValueError as e:
    print(f"Invalid input: {e}")
```

### Event Callbacks

Register callbacks to be notified of identity management events:

```python
def on_new_identity(event_data):
    print(f"New identity added: {event_data['identity']}")
    print(f"Permission level: {event_data['permission_level']}")
    print(f"Embeddings: {event_data['num_embeddings']}")

def on_permission_changed(event_data):
    print(f"Permission changed for: {event_data['identity']}")
    print(f"New level: {event_data['new_permission_level']}")

engine.register_callback('new_identity', on_new_identity)
engine.register_callback('permission_changed', on_permission_changed)
```

---

## Workflow Examples

### Adding Multiple Identities

```python
# Batch add multiple identities
identities_to_add = [
    ("Alice Johnson", "admin", ["alice1.jpg", "alice2.jpg", ...]),
    ("Bob Smith", "user", ["bob1.jpg", "bob2.jpg", ...]),
    ("Charlie Brown", "guest", ["charlie1.jpg", "charlie2.jpg", ...]),
]

for name, permission, image_paths in identities_to_add:
    images = [cv2.imread(path) for path in image_paths]
    success = engine.add_identity(name, images, permission)
    print(f"{'✓' if success else '✗'} {name}")
```

### Updating User Roles

```python
# Promote a user to admin
engine.update_permission("Bob Smith", "admin")

# Demote an admin to user
engine.update_permission("Alice Johnson", "user")

# Deny access to a user
engine.update_permission("Charlie Brown", "denied")
```

### Database Maintenance

```python
# Get all identities
identities = engine.get_identities()

# Remove identities with no embeddings (cleanup)
for identity in identities:
    if identity.num_embeddings == 0:
        engine.remove_identity(identity.name)
        print(f"Removed {identity.name} (no embeddings)")

# List all admin users
admins = [i for i in identities if i.permission_level == "admin"]
print(f"Admin users: {[a.name for a in admins]}")
```

---

## Technical Details

### Embedding Extraction Process

When you call `add_identity()`, the following happens for each image:

1. **Face Detection**: RetinaFace detects faces in the image
2. **Face Alignment**: Landmarks are used to align the face to 112x112 pixels
3. **Embedding Extraction**: The ONNX model generates a 512-dimensional vector
4. **Storage**: The embedding is stored with metadata (timestamp, angle, lighting)

### Database Persistence

- All changes are immediately saved to disk (Requirement 16.2)
- Database is stored in JSON format with base64-encoded embeddings
- Default location: `guru_face/database/identities.json`
- Automatic backup on modifications

### Recognition After Addition

- Newly added identities are immediately available for recognition (Requirement 16.3)
- No model retraining required (Requirement 16.1)
- Recognition uses cosine similarity between embeddings
- Multiple embeddings per identity improve accuracy across different conditions

---

## Troubleshooting

### "Engine not initialized" Error

Make sure to call `initialize()` before using identity management methods:

```python
engine = GuruVisionEngine()
engine.initialize()  # Required!
engine.add_identity(...)
```

### "No face detected" Warnings

If many images fail face detection:
- Check image quality and lighting
- Ensure faces are clearly visible
- Verify images are in BGR format (OpenCV default)
- Try different images with better face visibility

### Low Recognition Accuracy

If newly added identities are not recognized well:
- Add more images (aim for 10+ images)
- Include more variety in angles and lighting
- Ensure images are high quality
- Check that the recognition threshold is appropriate

### Permission Level Not Working

If permission levels don't seem to apply:
- Verify the AI agent is checking the `permission_level` field in recognition results
- Check that callbacks are registered for permission events
- Ensure the database was saved after updates

---

## See Also

- [Engine API Documentation](README_ENGINE.md)
- [Training Pipeline](training/README.md)
- [Database Module](database/README.md)
- [Example Scripts](example_identity_management.py)
