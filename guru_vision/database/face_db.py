"""
Face Database Module for GuruVision Facial Recognition System

This module provides data structures and database management for storing
and retrieving face embeddings and identity information.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np
import logging

from guru_vision.exceptions import DatabaseError

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class Embedding:
    """
    Represents a single face embedding with metadata.
    
    Attributes:
        vector: 512-dimensional embedding vector (numpy array)
        timestamp: ISO format timestamp of when embedding was created
        angle_category: Face angle category (frontal, profile, 45_degree)
        lighting_condition: Lighting condition (normal, low_light, bright)
        metadata: Additional custom metadata
    """
    vector: np.ndarray  # (512,) float32 array
    timestamp: str
    angle_category: str = "frontal"  # frontal, profile, 45_degree
    lighting_condition: str = "normal"  # normal, low_light, bright
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate embedding vector dimensions."""
        if not isinstance(self.vector, np.ndarray):
            raise TypeError("Embedding vector must be a numpy array")
        if self.vector.shape != (512,):
            raise ValueError(f"Embedding vector must be 512-dimensional, got shape {self.vector.shape}")


@dataclass
class Identity:
    """
    Represents a person's identity with multiple face embeddings.
    
    Attributes:
        name: Unique identifier/name for the identity
        embeddings: List of face embeddings from different angles/conditions
        permission_level: Access control level (admin, user, guest, denied)
        date_added: ISO format timestamp of when identity was first added
        metadata: Additional custom metadata
    """
    name: str
    embeddings: List[Embedding] = field(default_factory=list)
    permission_level: str = "user"  # admin, user, guest, denied
    date_added: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate permission level."""
        valid_levels = {"admin", "user", "guest", "denied"}
        if self.permission_level not in valid_levels:
            raise ValueError(f"Permission level must be one of {valid_levels}, got '{self.permission_level}'")



class FaceDatabase:
    """
    In-memory face database with persistence support.
    
    Manages storage and retrieval of face embeddings and identity information.
    Supports CRUD operations and identity matching via cosine similarity.
    """
    
    def __init__(self, db_path: str = "guru_face/database/identities.json"):
        """
        Initialize the face database.
        
        Args:
            db_path: Path to the JSON database file for persistence
        """
        self.db_path = db_path
        self.identities: Dict[str, Identity] = {}
        
    def add_identity(
        self, 
        name: str, 
        embeddings: List[np.ndarray], 
        permission_level: str = "user",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a new identity to the database.
        
        Args:
            name: Unique identifier for the identity
            embeddings: List of embedding vectors (each 512-dimensional)
            permission_level: Access control level (admin, user, guest, denied)
            metadata: Optional additional metadata
            
        Returns:
            True if identity was added successfully, False if identity already exists
            
        Raises:
            ValueError: If embeddings list is empty or contains invalid vectors
        """
        if name in self.identities:
            return False
            
        if not embeddings:
            raise ValueError("At least one embedding is required")
            
        # Create Embedding objects from numpy arrays
        embedding_objects = []
        timestamp = datetime.utcnow().isoformat()
        
        for emb_vector in embeddings:
            if not isinstance(emb_vector, np.ndarray) or emb_vector.shape != (512,):
                raise ValueError(f"Each embedding must be a 512-dimensional numpy array")
            
            embedding_obj = Embedding(
                vector=emb_vector,
                timestamp=timestamp,
                metadata={}
            )
            embedding_objects.append(embedding_obj)
        
        # Create Identity object
        identity = Identity(
            name=name,
            embeddings=embedding_objects,
            permission_level=permission_level,
            date_added=timestamp,
            metadata=metadata or {}
        )
        
        self.identities[name] = identity
        return True
    
    def add_embedding(
        self,
        name: str,
        embedding: np.ndarray,
        angle_category: str = "frontal",
        lighting_condition: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add an embedding to an existing identity.
        
        Args:
            name: Identity name
            embedding: 512-dimensional embedding vector
            angle_category: Face angle category
            lighting_condition: Lighting condition
            metadata: Optional additional metadata
            
        Returns:
            True if embedding was added, False if identity doesn't exist
            
        Raises:
            ValueError: If embedding is invalid
        """
        if name not in self.identities:
            return False
            
        if not isinstance(embedding, np.ndarray) or embedding.shape != (512,):
            raise ValueError("Embedding must be a 512-dimensional numpy array")
        
        embedding_obj = Embedding(
            vector=embedding,
            timestamp=datetime.utcnow().isoformat(),
            angle_category=angle_category,
            lighting_condition=lighting_condition,
            metadata=metadata or {}
        )
        
        self.identities[name].embeddings.append(embedding_obj)
        return True
    
    def get_identity(self, name: str) -> Optional[Identity]:
        """
        Retrieve an identity by name.
        
        Args:
            name: Identity name
            
        Returns:
            Identity object if found, None otherwise
        """
        return self.identities.get(name)
    
    def get_all_identities(self) -> List[Identity]:
        """
        Get all stored identities.
        
        Returns:
            List of all Identity objects in the database
        """
        return list(self.identities.values())

    
    def save(self) -> None:
        """
        Persist the database to disk in JSON format.
        
        Embeddings are base64-encoded for JSON serialization.
        Creates parent directories if they don't exist.
        
        Raises:
            DatabaseError: If file cannot be written or serialization fails
        """
        import json
        import base64
        import os
        
        try:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Serialize database to JSON-compatible format
            data = {
                "version": "1.0",
                "identities": []
            }
            
            for identity in self.identities.values():
                identity_data = {
                    "name": identity.name,
                    "permission_level": identity.permission_level,
                    "date_added": identity.date_added,
                    "metadata": identity.metadata,
                    "embeddings": []
                }
                
                for embedding in identity.embeddings:
                    # Base64 encode the numpy array
                    embedding_bytes = embedding.vector.tobytes()
                    embedding_b64 = base64.b64encode(embedding_bytes).decode('utf-8')
                    
                    embedding_data = {
                        "vector": embedding_b64,
                        "timestamp": embedding.timestamp,
                        "angle_category": embedding.angle_category,
                        "lighting_condition": embedding.lighting_condition,
                        "metadata": embedding.metadata
                    }
                    identity_data["embeddings"].append(embedding_data)
                
                data["identities"].append(identity_data)
            
            # Write to file
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Database saved successfully to {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to save database to {self.db_path}: {e}")
            raise DatabaseError(f"Failed to save database: {e}") from e
    
    def load(self) -> None:
        """
        Load the database from disk.
        
        Decodes base64-encoded embeddings back to numpy arrays.
        If file doesn't exist, initializes empty database.
        
        Raises:
            DatabaseError: If file exists but cannot be read or format is invalid
        """
        import json
        import base64
        import os
        
        if not os.path.exists(self.db_path):
            # Initialize empty database
            self.identities = {}
            logger.info(f"Database file not found at {self.db_path}, initialized empty database")
            return
        
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
            
            # Validate version
            if "version" not in data:
                raise DatabaseError("Database file missing version field")
            
            # Clear existing identities
            self.identities = {}
            
            # Load identities
            for identity_data in data.get("identities", []):
                embeddings = []
                
                for emb_data in identity_data.get("embeddings", []):
                    # Decode base64 to numpy array
                    embedding_b64 = emb_data["vector"]
                    embedding_bytes = base64.b64decode(embedding_b64)
                    embedding_vector = np.frombuffer(embedding_bytes, dtype=np.float32)
                    
                    # Ensure correct shape
                    if embedding_vector.shape != (512,):
                        raise DatabaseError(f"Invalid embedding shape: {embedding_vector.shape}")
                    
                    embedding = Embedding(
                        vector=embedding_vector,
                        timestamp=emb_data["timestamp"],
                        angle_category=emb_data.get("angle_category", "frontal"),
                        lighting_condition=emb_data.get("lighting_condition", "normal"),
                        metadata=emb_data.get("metadata", {})
                    )
                    embeddings.append(embedding)
                
                identity = Identity(
                    name=identity_data["name"],
                    embeddings=embeddings,
                    permission_level=identity_data.get("permission_level", "user"),
                    date_added=identity_data.get("date_added", datetime.utcnow().isoformat()),
                    metadata=identity_data.get("metadata", {})
                )
                
                self.identities[identity.name] = identity
            
            logger.info(f"Database loaded successfully from {self.db_path} with {len(self.identities)} identities")
            
        except DatabaseError:
            # Re-raise DatabaseError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to load database from {self.db_path}: {e}")
            raise DatabaseError(f"Failed to load database: {e}") from e

    
    def search(
        self, 
        embedding: np.ndarray, 
        threshold: float = 0.6
    ) -> Optional[Dict[str, Any]]:
        """
        Search for the best matching identity using cosine similarity.
        
        Compares the query embedding against all stored embeddings for each identity
        and returns the best match if it exceeds the threshold.
        
        Args:
            embedding: Query embedding vector (512-dimensional)
            threshold: Minimum similarity score required for a match (0.0 to 1.0)
            
        Returns:
            Dictionary with keys: 'identity', 'confidence', 'permission_level'
            Returns None if no match exceeds threshold
            
        Raises:
            ValueError: If embedding is invalid or threshold is out of range
        """
        if not isinstance(embedding, np.ndarray) or embedding.shape != (512,):
            raise ValueError("Query embedding must be a 512-dimensional numpy array")
        
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")
        
        best_match = None
        best_similarity = -1.0
        
        # Search through all identities
        for identity in self.identities.values():
            # Compare against all embeddings for this identity
            for stored_embedding in identity.embeddings:
                similarity = self._cosine_similarity(embedding, stored_embedding.vector)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = identity
        
        # Return match if above threshold
        if best_match is not None and best_similarity >= threshold:
            return {
                "identity": best_match.name,
                "confidence": float(best_similarity),
                "permission_level": best_match.permission_level
            }
        
        return None
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score between 0.0 and 1.0
        """
        # Compute dot product
        dot_product = np.dot(vec1, vec2)
        
        # Compute magnitudes
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        # Avoid division by zero
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Compute cosine similarity
        similarity = dot_product / (norm1 * norm2)
        
        # Clamp to [0, 1] range (handle floating point errors)
        return float(np.clip(similarity, 0.0, 1.0))

    
    def update_permission(self, name: str, permission_level: str) -> bool:
        """
        Update the permission level for an identity.
        
        Args:
            name: Identity name
            permission_level: New permission level (admin, user, guest, denied)
            
        Returns:
            True if updated successfully, False if identity doesn't exist
            
        Raises:
            ValueError: If permission_level is invalid
        """
        if name not in self.identities:
            return False
        
        valid_levels = {"admin", "user", "guest", "denied"}
        if permission_level not in valid_levels:
            raise ValueError(f"Permission level must be one of {valid_levels}, got '{permission_level}'")
        
        self.identities[name].permission_level = permission_level
        return True
    
    def remove_identity(self, name: str) -> bool:
        """
        Remove an identity and all associated embeddings from the database.
        
        Args:
            name: Identity name
            
        Returns:
            True if identity was removed, False if identity doesn't exist
        """
        if name not in self.identities:
            return False
        
        del self.identities[name]
        return True

    
    def export_json(self, export_path: str) -> None:
        """
        Export the database to a JSON file at the specified path.
        
        This is similar to save() but allows exporting to a different location
        for backup or transfer purposes.
        
        Args:
            export_path: Path where the JSON file should be saved
            
        Raises:
            IOError: If file cannot be written
        """
        import json
        import base64
        import os
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
        # Serialize database to JSON-compatible format
        data = {
            "version": "1.0",
            "identities": []
        }
        
        for identity in self.identities.values():
            identity_data = {
                "name": identity.name,
                "permission_level": identity.permission_level,
                "date_added": identity.date_added,
                "metadata": identity.metadata,
                "embeddings": []
            }
            
            for embedding in identity.embeddings:
                # Base64 encode the numpy array
                embedding_bytes = embedding.vector.tobytes()
                embedding_b64 = base64.b64encode(embedding_bytes).decode('utf-8')
                
                embedding_data = {
                    "vector": embedding_b64,
                    "timestamp": embedding.timestamp,
                    "angle_category": embedding.angle_category,
                    "lighting_condition": embedding.lighting_condition,
                    "metadata": embedding.metadata
                }
                identity_data["embeddings"].append(embedding_data)
            
            data["identities"].append(identity_data)
        
        # Write to file
        with open(export_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def import_json(self, import_path: str, merge: bool = False) -> None:
        """
        Import identities from a JSON file.
        
        Args:
            import_path: Path to the JSON file to import
            merge: If True, merge with existing identities. If False, replace all identities.
            
        Raises:
            IOError: If file cannot be read
            ValueError: If file format is invalid
        """
        import json
        import base64
        import os
        
        if not os.path.exists(import_path):
            raise IOError(f"Import file not found: {import_path}")
        
        with open(import_path, 'r') as f:
            data = json.load(f)
        
        # Validate version
        if "version" not in data:
            raise ValueError("Import file missing version field")
        
        # Clear existing identities if not merging
        if not merge:
            self.identities = {}
        
        # Load identities
        for identity_data in data.get("identities", []):
            embeddings = []
            
            for emb_data in identity_data.get("embeddings", []):
                # Decode base64 to numpy array
                embedding_b64 = emb_data["vector"]
                embedding_bytes = base64.b64decode(embedding_b64)
                embedding_vector = np.frombuffer(embedding_bytes, dtype=np.float32)
                
                # Ensure correct shape
                if embedding_vector.shape != (512,):
                    raise ValueError(f"Invalid embedding shape: {embedding_vector.shape}")
                
                embedding = Embedding(
                    vector=embedding_vector,
                    timestamp=emb_data["timestamp"],
                    angle_category=emb_data.get("angle_category", "frontal"),
                    lighting_condition=emb_data.get("lighting_condition", "normal"),
                    metadata=emb_data.get("metadata", {})
                )
                embeddings.append(embedding)
            
            identity = Identity(
                name=identity_data["name"],
                embeddings=embeddings,
                permission_level=identity_data.get("permission_level", "user"),
                date_added=identity_data.get("date_added", datetime.utcnow().isoformat()),
                metadata=identity_data.get("metadata", {})
            )
            
            # Add or update identity
            self.identities[identity.name] = identity
