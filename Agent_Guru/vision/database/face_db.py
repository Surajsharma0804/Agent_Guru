"""
Face database module for GuruVision facial recognition system.

Stores identity embeddings and metadata with multi-angle memory support,
permission-based access control, and JSON persistence.

Performance Characteristics:
    - Time Complexity: O(n*m) for search (n identities, m embeddings each)
    - Space Complexity: O(n*m) for in-memory storage
    - Persistence: JSON with base64-encoded embedding vectors

Design:
    All identities are loaded into memory at startup for fast lookups.
    Modifications are auto-saved to disk immediately.
    Cosine similarity is computed as dot product of L2-normalised vectors.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from Agent_Guru.security.embedding_auth import BIOMETRIC_THRESHOLD, verify_embedding

logger = logging.getLogger(__name__)

# Valid permission levels
VALID_PERMISSION_LEVELS = frozenset({"admin", "user", "guest", "denied"})


@dataclass
class Embedding:
    """A single face embedding with capture metadata.

    Attributes:
        vector: 512-dimensional L2-normalised float32 embedding vector.
        timestamp: ISO 8601 capture timestamp.
        angle_category: Head pose category at capture time.
        lighting_condition: Lighting category at capture time.
        metadata: Arbitrary extra metadata.
    """

    vector: np.ndarray  # shape (512,), float32, L2-normalised
    timestamp: str  # ISO format
    angle_category: str  # "frontal", "profile", "45_degree"
    lighting_condition: str  # "normal", "low_light", "bright"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Identity:
    """A known person with stored face embeddings and access metadata.

    Attributes:
        name: Unique display name for this identity.
        embeddings: All stored face embeddings for this person.
        permission_level: RBAC level: "admin", "user", "guest", or "denied".
        date_added: ISO 8601 timestamp when the identity was first added.
        metadata: Arbitrary extra metadata.
    """

    name: str
    embeddings: list[Embedding]
    permission_level: str  # "admin", "user", "guest", "denied"
    date_added: str  # ISO format
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchResult:
    """Result of a database similarity search.

    Attributes:
        identity: Matched identity name, or "Unknown" if no match found.
        confidence: Cosine similarity score of the best match (0.0–1.0).
        permission_level: Permission level of the matched identity.
    """

    identity: str  # name or "Unknown"
    confidence: float  # cosine similarity score
    permission_level: str


def _l2_normalise(vector: np.ndarray) -> np.ndarray:
    """Return an L2-normalised copy of *vector*.

    If the vector has zero norm it is returned unchanged to avoid division
    by zero.

    Args:
        vector: Input float array.

    Returns:
        Unit-length float32 array with the same shape.
    """
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector.astype(np.float32)
    result: np.ndarray = (vector / norm).astype(np.float32)
    return result


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class FaceDatabase:
    """In-memory face identity database with JSON persistence.

    All identities are loaded into memory at startup for O(1) name lookups.
    Embedding search is O(n*m) where n is the number of identities and m is
    the average number of embeddings per identity.

    Cosine similarity between two L2-normalised vectors reduces to their dot
    product, which is computed with ``np.dot``.

    Example:
        >>> db = FaceDatabase()
        >>> import numpy as np
        >>> emb = np.random.randn(512).astype(np.float32)
        >>> db.add_identity("Alice", [emb], permission_level="user")
        True
        >>> result = db.search(emb)
        >>> result.identity
        'Alice'
    """

    def __init__(
        self,
        db_path: str = "Agent_Guru/vision/data/database/identities.json",
    ) -> None:
        """Initialise the database and load existing data from disk.

        Creates parent directories for *db_path* if they do not exist.
        If the file does not exist, the database starts empty (no error).

        Args:
            db_path: Path to the JSON persistence file.
        """
        self._db_path = db_path
        self._identities: dict[str, Identity] = {}

        # Ensure parent directory exists
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self.load()

    # ------------------------------------------------------------------
    # Public CRUD API
    # ------------------------------------------------------------------

    def add_identity(
        self,
        name: str,
        embeddings: list[np.ndarray],
        permission_level: str = "user",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Add a new identity with one or more embeddings.

        If an identity with *name* already exists it is replaced.

        Args:
            name: Unique name for the identity.
            embeddings: List of raw embedding vectors (will be L2-normalised).
            permission_level: RBAC level ("admin", "user", "guest", "denied").
            metadata: Optional extra metadata dict.

        Returns:
            True on success, False if *embeddings* is empty or *name* is blank.
        """
        if not name or not name.strip():
            logger.warning("add_identity: name must not be empty")
            return False
        if not embeddings:
            logger.warning("add_identity: embeddings list must not be empty")
            return False
        if permission_level not in VALID_PERMISSION_LEVELS:
            logger.warning(
                "add_identity: unknown permission_level %r, defaulting to 'user'",
                permission_level,
            )
            permission_level = "user"

        now = _now_iso()
        embedding_objects = [
            Embedding(
                vector=_l2_normalise(vec),
                timestamp=now,
                angle_category="frontal",
                lighting_condition="normal",
            )
            for vec in embeddings
        ]

        self._identities[name] = Identity(
            name=name,
            embeddings=embedding_objects,
            permission_level=permission_level,
            date_added=now,
            metadata=dict(metadata) if metadata else {},
        )
        logger.info("add_identity: added '%s' with %d embedding(s)", name, len(embeddings))
        self.save()
        return True

    def add_embedding(
        self,
        name: str,
        embedding: np.ndarray,
        angle_category: str = "frontal",
        lighting_condition: str = "normal",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Append a single embedding to an existing identity.

        Args:
            name: Name of the existing identity.
            embedding: Raw embedding vector (will be L2-normalised).
            angle_category: Head pose category ("frontal", "profile", "45_degree").
            lighting_condition: Lighting category ("normal", "low_light", "bright").
            metadata: Optional extra metadata for this embedding.

        Returns:
            True on success, False if the identity does not exist.
        """
        if name not in self._identities:
            logger.warning("add_embedding: identity '%s' not found", name)
            return False

        emb = Embedding(
            vector=_l2_normalise(embedding),
            timestamp=_now_iso(),
            angle_category=angle_category,
            lighting_condition=lighting_condition,
            metadata=dict(metadata) if metadata else {},
        )
        self._identities[name].embeddings.append(emb)
        logger.debug("add_embedding: appended embedding to '%s'", name)
        self.save()
        return True

    def get_identity(self, name: str) -> Optional[Identity]:
        """Retrieve an identity by name.

        Args:
            name: Identity name to look up.

        Returns:
            The :class:`Identity` object, or ``None`` if not found.
        """
        return self._identities.get(name)

    def get_all_identities(self) -> list[Identity]:
        """Return all stored identities.

        Returns:
            List of all :class:`Identity` objects (may be empty).
        """
        return list(self._identities.values())

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        embedding: np.ndarray,
        threshold: float = BIOMETRIC_THRESHOLD,
    ) -> MatchResult:
        """Find the best matching identity for *embedding*.

        Computes cosine similarity (dot product of L2-normalised vectors)
        against every stored embedding for every identity and returns the
        best match above *threshold*.

        Args:
            embedding: Query embedding vector (will be L2-normalised).
            threshold: Minimum similarity score to accept a match (0.0–1.0).
                Defaults to :data:`~Agent_Guru.security.embedding_auth.BIOMETRIC_THRESHOLD`
                (0.97) to enforce FAR < 0.1%.

        Returns:
            :class:`MatchResult` with the best match, or
            ``MatchResult("Unknown", 0.0, "guest")`` if no match exceeds
            *threshold* or the database is empty.
        """
        query = _l2_normalise(embedding)

        best_score = -1.0
        best_name: Optional[str] = None
        best_emb_vector: Optional[np.ndarray] = None

        for identity in self._identities.values():
            for emb in identity.embeddings:
                score = float(np.dot(query, emb.vector))
                if score > best_score:
                    best_score = score
                    best_name = identity.name
                    best_emb_vector = emb.vector

        if (
            best_name is not None
            and best_emb_vector is not None
            and verify_embedding(query, best_emb_vector, threshold)
        ):
            identity = self._identities[best_name]
            return MatchResult(
                identity=best_name,
                confidence=best_score,
                permission_level=identity.permission_level,
            )

        return MatchResult(identity="Unknown", confidence=0.0, permission_level="guest")

    # ------------------------------------------------------------------
    # Update / Delete
    # ------------------------------------------------------------------

    def update_permission(self, name: str, permission_level: str) -> bool:
        """Update the permission level for an existing identity.

        Args:
            name: Identity name.
            permission_level: New RBAC level.

        Returns:
            True on success, False if the identity does not exist or the
            permission level is invalid.
        """
        if name not in self._identities:
            logger.warning("update_permission: identity '%s' not found", name)
            return False
        if permission_level not in VALID_PERMISSION_LEVELS:
            logger.warning(
                "update_permission: invalid permission_level %r", permission_level
            )
            return False

        self._identities[name].permission_level = permission_level
        logger.info("update_permission: '%s' → '%s'", name, permission_level)
        self.save()
        return True

    def remove_identity(self, name: str) -> bool:
        """Remove an identity and all its embeddings.

        Args:
            name: Identity name to remove.

        Returns:
            True if the identity was found and removed, False otherwise.
        """
        if name not in self._identities:
            logger.warning("remove_identity: identity '%s' not found", name)
            return False

        del self._identities[name]
        logger.info("remove_identity: removed '%s'", name)
        self.save()
        return True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the database to disk as JSON.

        Embedding vectors are base64-encoded for compact, lossless storage.
        The file is written atomically via a temporary name then renamed.
        """
        data = self._serialise()
        tmp_path = self._db_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp_path, self._db_path)
            logger.debug("save: database written to '%s'", self._db_path)
        except OSError as exc:
            logger.error("save: failed to write database: %s", exc)
            # Clean up temp file if it exists
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def load(self) -> None:
        """Load the database from disk.

        If the file does not exist the database starts empty (no error).
        Embedding vectors are base64-decoded back to float32 numpy arrays.
        """
        if not os.path.exists(self._db_path):
            logger.debug("load: no database file at '%s', starting empty", self._db_path)
            self._identities = {}
            return

        try:
            with open(self._db_path, encoding="utf-8") as fh:
                data = json.load(fh)
            self._identities = self._deserialise(data)
            logger.info(
                "load: loaded %d identity/identities from '%s'",
                len(self._identities),
                self._db_path,
            )
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("load: failed to load database: %s", exc)
            self._identities = {}

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def export_json(self) -> str:
        """Export the entire database as a JSON string.

        Returns:
            JSON-encoded string representing all identities and embeddings.
        """
        return json.dumps(self._serialise(), indent=2)

    def import_json(self, json_str: str) -> bool:
        """Import identities from a JSON string, merging with existing data.

        Identities in *json_str* overwrite existing identities with the same
        name.  Identities not present in *json_str* are preserved.

        Args:
            json_str: JSON string previously produced by :meth:`export_json`.

        Returns:
            True on success, False if the JSON is invalid.
        """
        try:
            data = json.loads(json_str)
            imported = self._deserialise(data)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("import_json: failed to parse JSON: %s", exc)
            return False

        self._identities.update(imported)
        logger.info("import_json: imported %d identity/identities", len(imported))
        self.save()
        return True

    # ------------------------------------------------------------------
    # Internal serialisation helpers
    # ------------------------------------------------------------------

    def _serialise(self) -> dict[str, Any]:
        """Convert in-memory state to a JSON-serialisable dict."""
        identities_list = []
        for identity in self._identities.values():
            embeddings_list = []
            for emb in identity.embeddings:
                raw = emb.vector.astype(np.float32).tobytes()
                b64 = base64.b64encode(raw).decode("ascii")
                embeddings_list.append(
                    {
                        "vector": b64,
                        "timestamp": emb.timestamp,
                        "angle_category": emb.angle_category,
                        "lighting_condition": emb.lighting_condition,
                        "metadata": emb.metadata,
                    }
                )
            identities_list.append(
                {
                    "name": identity.name,
                    "embeddings": embeddings_list,
                    "permission_level": identity.permission_level,
                    "date_added": identity.date_added,
                    "metadata": identity.metadata,
                }
            )
        return {"version": "1.0", "identities": identities_list}

    @staticmethod
    def _deserialise(data: dict[str, Any]) -> dict[str, Identity]:
        """Reconstruct in-memory state from a JSON-deserialised dict."""
        identities: dict[str, Identity] = {}
        for id_data in data.get("identities", []):
            embeddings = []
            for emb_data in id_data.get("embeddings", []):
                raw = base64.b64decode(emb_data["vector"])
                vector = np.frombuffer(raw, dtype=np.float32).copy()
                embeddings.append(
                    Embedding(
                        vector=vector,
                        timestamp=emb_data.get("timestamp", ""),
                        angle_category=emb_data.get("angle_category", "frontal"),
                        lighting_condition=emb_data.get("lighting_condition", "normal"),
                        metadata=emb_data.get("metadata", {}),
                    )
                )
            name = id_data["name"]
            identities[name] = Identity(
                name=name,
                embeddings=embeddings,
                permission_level=id_data.get("permission_level", "user"),
                date_added=id_data.get("date_added", ""),
                metadata=id_data.get("metadata", {}),
            )
        return identities
