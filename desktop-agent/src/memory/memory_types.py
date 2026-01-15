"""
MIRIX Memory Types Implementation

Defines the six specialized memory types for the GURU Personal Assistant:
1. Core Memory: Persistent user preferences and identity
2. Episodic Memory: Time-based activities and events  
3. Semantic Memory: General knowledge and concepts
4. Procedural Memory: Workflows and step-by-step processes
5. Resource Memory: Documents and active files
6. Knowledge Vault: Encrypted sensitive data (credentials, contacts)

Each memory type provides:
- Type-specific data models and validation
- Specialized storage and retrieval operations
- Encryption support for sensitive data
- Vector embedding support for similarity search
- Configurable retention policies
"""

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataType(Enum):
    """Supported data types for memory storage."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"


class RetentionPolicy(Enum):
    """Memory retention policies."""
    SHORT_TERM = "short_term"      # Days to weeks
    MEDIUM_TERM = "medium_term"    # Weeks to months
    LONG_TERM = "long_term"        # Months to years
    PERMANENT = "permanent"        # Never auto-delete


class AccessPolicy(Enum):
    """Access control policies for sensitive data."""
    STRICT = "strict"      # Require explicit authorization
    NORMAL = "normal"      # Standard access controls
    RELAXED = "relaxed"    # Minimal access controls


@dataclass
class BaseMemoryRecord(ABC):
    """Base class for all memory records."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    encrypted: bool = False
    vector_embedding: Optional[bytes] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for storage."""
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseMemoryRecord':
        """Create record from dictionary."""
    
    def update_timestamp(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class CoreMemory(BaseMemoryRecord):
    """
    Core Memory: Persistent user preferences and identity.
    
    Stores fundamental user configuration, preferences, and identity information
    that persists across sessions and forms the foundation of user personalization.
    """
    key: str = ""
    value: Any = None
    data_type: DataType = DataType.STRING
    version: int = 1
    
    def __post_init__(self):
        super().__post_init__()
        if not self.key:
            raise ValueError("Core memory key cannot be empty")
        if self.value is None:
            raise ValueError("Core memory value cannot be None")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        # Serialize value based on data type
        if self.data_type == DataType.JSON:
            serialized_value = json.dumps(self.value)
        else:
            serialized_value = str(self.value)
        
        return {
            'id': self.id,
            'key': self.key,
            'value': serialized_value,
            'data_type': self.data_type.value,
            'encrypted': self.encrypted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CoreMemory':
        """Create CoreMemory from database row."""
        data_type = DataType(data['data_type'])
        
        # Deserialize value based on data type
        raw_value = data['value']
        if data_type == DataType.JSON:
            value = json.loads(raw_value)
        elif data_type == DataType.INTEGER:
            value = int(raw_value)
        elif data_type == DataType.FLOAT:
            value = float(raw_value)
        elif data_type == DataType.BOOLEAN:
            value = raw_value.lower() in ('true', '1', 'yes')
        else:
            value = raw_value
        
        return cls(
            id=data.get('id'),
            key=data['key'],
            value=value,
            data_type=data_type,
            encrypted=data.get('encrypted', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            version=data.get('version', 1)
        )


@dataclass
class EpisodicMemory(BaseMemoryRecord):
    """
    Episodic Memory: Time-based activities and events.
    
    Stores specific events, interactions, and activities with temporal context.
    Used for remembering what happened when and building contextual understanding.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    summary: str = ""
    details: Optional[str] = None
    participants: List[str] = field(default_factory=list)
    location: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    confidence_score: float = 1.0
    occurred_at: Optional[datetime] = None
    retention_policy: RetentionPolicy = RetentionPolicy.SHORT_TERM
    
    def __post_init__(self):
        super().__post_init__()
        if not self.summary:
            raise ValueError("Episodic memory summary cannot be empty")
        if self.occurred_at is None:
            self.occurred_at = datetime.now(timezone.utc)
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'event_id': self.event_id,
            'summary': self.summary,
            'details': self.details,
            'participants': json.dumps(self.participants),
            'location': self.location,
            'tags': json.dumps(self.tags),
            'confidence_score': self.confidence_score,
            'encrypted': self.encrypted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'occurred_at': self.occurred_at.isoformat() if self.occurred_at else None,
            'retention_policy': self.retention_policy.value,
            'vector_embedding': self.vector_embedding
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EpisodicMemory':
        """Create EpisodicMemory from database row."""
        return cls(
            id=data.get('id'),
            event_id=data['event_id'],
            summary=data['summary'],
            details=data.get('details'),
            participants=json.loads(data.get('participants', '[]')),
            location=data.get('location'),
            tags=json.loads(data.get('tags', '[]')),
            confidence_score=data.get('confidence_score', 1.0),
            encrypted=data.get('encrypted', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            occurred_at=datetime.fromisoformat(data['occurred_at']) if data.get('occurred_at') else None,
            retention_policy=RetentionPolicy(data.get('retention_policy', 'short_term')),
            vector_embedding=data.get('vector_embedding')
        )


@dataclass
class SemanticMemory(BaseMemoryRecord):
    """
    Semantic Memory: General knowledge and concepts.
    
    Stores conceptual knowledge, relationships between concepts, and general
    understanding that builds over time through interactions and learning.
    """
    concept_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    concept_name: str = ""
    description: Optional[str] = None
    category: Optional[str] = None
    relationships: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 1.0
    usage_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def __post_init__(self):
        super().__post_init__()
        if not self.concept_name:
            raise ValueError("Semantic memory concept name cannot be empty")
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        if self.last_accessed is None:
            self.last_accessed = datetime.now(timezone.utc)
    
    def increment_usage(self) -> None:
        """Increment usage count and update last accessed time."""
        self.usage_count += 1
        self.last_accessed = datetime.now(timezone.utc)
        self.update_timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'concept_id': self.concept_id,
            'concept_name': self.concept_name,
            'description': self.description,
            'category': self.category,
            'relationships': json.dumps(self.relationships),
            'confidence_score': self.confidence_score,
            'usage_count': self.usage_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'encrypted': self.encrypted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'vector_embedding': self.vector_embedding
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SemanticMemory':
        """Create SemanticMemory from database row."""
        return cls(
            id=data.get('id'),
            concept_id=data['concept_id'],
            concept_name=data['concept_name'],
            description=data.get('description'),
            category=data.get('category'),
            relationships=json.loads(data.get('relationships', '{}')),
            confidence_score=data.get('confidence_score', 1.0),
            usage_count=data.get('usage_count', 0),
            last_accessed=datetime.fromisoformat(data['last_accessed']) if data.get('last_accessed') else None,
            encrypted=data.get('encrypted', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            vector_embedding=data.get('vector_embedding')
        )


@dataclass
class ProceduralMemory(BaseMemoryRecord):
    """
    Procedural Memory: Workflows and step-by-step processes.
    
    Stores learned procedures, workflows, and step-by-step processes that can
    be executed to accomplish tasks. Includes success tracking and optimization.
    """
    procedure_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    failure_handling: Dict[str, Any] = field(default_factory=dict)
    execution_count: int = 0
    success_rate: float = 0.0
    average_duration_ms: Optional[int] = None
    last_executed: Optional[datetime] = None
    
    def __post_init__(self):
        super().__post_init__()
        if not self.name:
            raise ValueError("Procedural memory name cannot be empty")
        if not self.steps:
            raise ValueError("Procedural memory must have at least one step")
        if not 0.0 <= self.success_rate <= 1.0:
            raise ValueError("Success rate must be between 0.0 and 1.0")
    
    def record_execution(self, success: bool, duration_ms: int) -> None:
        """Record an execution attempt and update statistics."""
        self.execution_count += 1
        self.last_executed = datetime.now(timezone.utc)
        
        # Update success rate
        if self.execution_count == 1:
            self.success_rate = 1.0 if success else 0.0
        else:
            # Weighted average favoring recent executions
            weight = 0.8
            self.success_rate = (weight * (1.0 if success else 0.0) + 
                               (1 - weight) * self.success_rate)
        
        # Update average duration
        if self.average_duration_ms is None:
            self.average_duration_ms = duration_ms
        else:
            # Exponential moving average
            alpha = 0.3
            self.average_duration_ms = int(
                alpha * duration_ms + (1 - alpha) * self.average_duration_ms
            )
        
        self.update_timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'procedure_id': self.procedure_id,
            'name': self.name,
            'description': self.description,
            'steps': json.dumps(self.steps),
            'prerequisites': json.dumps(self.prerequisites),
            'success_criteria': json.dumps(self.success_criteria),
            'failure_handling': json.dumps(self.failure_handling),
            'execution_count': self.execution_count,
            'success_rate': self.success_rate,
            'average_duration_ms': self.average_duration_ms,
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'encrypted': self.encrypted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'vector_embedding': self.vector_embedding
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProceduralMemory':
        """Create ProceduralMemory from database row."""
        return cls(
            id=data.get('id'),
            procedure_id=data['procedure_id'],
            name=data['name'],
            description=data.get('description'),
            steps=json.loads(data.get('steps', '[]')),
            prerequisites=json.loads(data.get('prerequisites', '[]')),
            success_criteria=json.loads(data.get('success_criteria', '[]')),
            failure_handling=json.loads(data.get('failure_handling', '{}')),
            execution_count=data.get('execution_count', 0),
            success_rate=data.get('success_rate', 0.0),
            average_duration_ms=data.get('average_duration_ms'),
            last_executed=datetime.fromisoformat(data['last_executed']) if data.get('last_executed') else None,
            encrypted=data.get('encrypted', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            vector_embedding=data.get('vector_embedding')
        )


@dataclass
class ResourceMemory(BaseMemoryRecord):
    """
    Resource Memory: Documents and active files.
    
    Stores references to and metadata about files, documents, URLs, and other
    resources that the user interacts with. Includes access tracking and content hashing.
    """
    resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: str = "file"  # file, document, url, reference
    path: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    retention_policy: RetentionPolicy = RetentionPolicy.LONG_TERM
    
    def __post_init__(self):
        super().__post_init__()
        if not self.name:
            raise ValueError("Resource memory name cannot be empty")
        if self.resource_type not in ['file', 'document', 'url', 'reference']:
            raise ValueError("Invalid resource type")
        if self.last_accessed is None:
            self.last_accessed = datetime.now(timezone.utc)
    
    def record_access(self) -> None:
        """Record an access to this resource."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
        self.update_timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'resource_id': self.resource_id,
            'name': self.name,
            'resource_type': self.resource_type,
            'path': self.path,
            'content_hash': self.content_hash,
            'metadata': json.dumps(self.metadata),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'encrypted': self.encrypted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'retention_policy': self.retention_policy.value,
            'vector_embedding': self.vector_embedding
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceMemory':
        """Create ResourceMemory from database row."""
        return cls(
            id=data.get('id'),
            resource_id=data['resource_id'],
            name=data['name'],
            resource_type=data['resource_type'],
            path=data.get('path'),
            content_hash=data.get('content_hash'),
            metadata=json.loads(data.get('metadata', '{}')),
            access_count=data.get('access_count', 0),
            last_accessed=datetime.fromisoformat(data['last_accessed']) if data.get('last_accessed') else None,
            file_size=data.get('file_size'),
            mime_type=data.get('mime_type'),
            encrypted=data.get('encrypted', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            retention_policy=RetentionPolicy(data.get('retention_policy', 'long_term')),
            vector_embedding=data.get('vector_embedding')
        )


@dataclass
class KnowledgeVault(BaseMemoryRecord):
    """
    Knowledge Vault: Encrypted sensitive data (credentials, contacts).
    
    Stores highly sensitive information with strong encryption and access controls.
    All data is encrypted at rest and requires explicit authorization to access.
    Credentials are stored as references or tokens only - never plaintext passwords.
    """
    vault_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    vault_type: str = "secret"  # credential, contact, secret, token
    encrypted_data: bytes = b""
    metadata: Dict[str, Any] = field(default_factory=dict)  # Non-sensitive metadata only
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    access_policy: AccessPolicy = AccessPolicy.STRICT
    
    def __post_init__(self):
        super().__post_init__()
        if not self.name:
            raise ValueError("Knowledge vault name cannot be empty")
        if self.vault_type not in ['credential', 'contact', 'secret', 'token']:
            raise ValueError("Invalid vault type")
        if not self.encrypted_data:
            raise ValueError("Knowledge vault encrypted data cannot be empty")
        if self.last_accessed is None:
            self.last_accessed = datetime.now(timezone.utc)
        # Knowledge vault data is ALWAYS encrypted
        self.encrypted = True
    
    def record_access(self) -> None:
        """Record an access to this vault item."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
        self.update_timestamp()
    
    def is_expired(self) -> bool:
        """Check if this vault item has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'vault_id': self.vault_id,
            'name': self.name,
            'vault_type': self.vault_type,
            'encrypted_data': self.encrypted_data,
            'metadata': json.dumps(self.metadata),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'access_policy': self.access_policy.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeVault':
        """Create KnowledgeVault from database row."""
        return cls(
            id=data.get('id'),
            vault_id=data['vault_id'],
            name=data['name'],
            vault_type=data['vault_type'],
            encrypted_data=data['encrypted_data'],
            metadata=json.loads(data.get('metadata', '{}')),
            access_count=data.get('access_count', 0),
            last_accessed=datetime.fromisoformat(data['last_accessed']) if data.get('last_accessed') else None,
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
            access_policy=AccessPolicy(data.get('access_policy', 'strict'))
        )