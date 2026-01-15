"""
Checkpoint Manager - Phase Validation and Safety Gates

Manages checkpoints between audit phases to ensure safety.
No phase can proceed without passing its checkpoint validation.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional


class CheckpointStatus(Enum):
    """Status of a checkpoint"""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CheckpointValidation:
    """Single validation within a checkpoint"""
    name: str
    description: str
    passed: bool
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class Checkpoint:
    """Checkpoint between audit phases"""
    name: str
    phase: str
    timestamp: datetime
    status: CheckpointStatus
    validations: List[CheckpointValidation] = field(default_factory=list)
    user_approved: bool = False
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Serialize checkpoint to dictionary"""
        return {
            'name': self.name,
            'phase': self.phase,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'validations': [
                {
                    'name': v.name,
                    'description': v.description,
                    'passed': v.passed,
                    'error_message': v.error_message,
                    'metadata': v.metadata,
                }
                for v in self.validations
            ],
            'user_approved': self.user_approved,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Checkpoint':
        """Deserialize checkpoint from dictionary"""
        checkpoint = cls(
            name=data['name'],
            phase=data['phase'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            status=CheckpointStatus(data['status']),
            user_approved=data['user_approved'],
            metadata=data.get('metadata', {}),
        )
        
        for v in data['validations']:
            checkpoint.validations.append(CheckpointValidation(
                name=v['name'],
                description=v['description'],
                passed=v['passed'],
                error_message=v.get('error_message'),
                metadata=v.get('metadata', {}),
            ))
        
        return checkpoint


class CheckpointManager:
    """
    Manages checkpoints and phase validation.
    
    Ensures no phase proceeds without passing validation.
    Provides safety gates between destructive operations.
    """
    
    def __init__(self, checkpoint_file: Path):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_file: Path to checkpoint persistence file
        """
        self.checkpoint_file = checkpoint_file.resolve()
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing checkpoints
        if self.checkpoint_file.exists():
            self.checkpoints = self._load_checkpoints()
        else:
            self.checkpoints: List[Checkpoint] = []
    
    def create_checkpoint(self, name: str, phase: str, metadata: Optional[Dict] = None) -> Checkpoint:
        """
        Create a new checkpoint.
        
        Args:
            name: Checkpoint name
            phase: Phase name
            metadata: Additional metadata
            
        Returns:
            Created checkpoint
        """
        checkpoint = Checkpoint(
            name=name,
            phase=phase,
            timestamp=datetime.now(),
            status=CheckpointStatus.PENDING,
            metadata=metadata or {},
        )
        
        self.checkpoints.append(checkpoint)
        self._save_checkpoints()
        
        return checkpoint
    
    def add_validation(
        self,
        checkpoint: Checkpoint,
        name: str,
        description: str,
        validation_func: Callable[[], bool],
        metadata: Optional[Dict] = None
    ) -> CheckpointValidation:
        """
        Add validation to checkpoint.
        
        Args:
            checkpoint: Checkpoint to add validation to
            name: Validation name
            description: Validation description
            validation_func: Function that performs validation (returns True if passed)
            metadata: Additional metadata
            
        Returns:
            Created validation
        """
        try:
            passed = validation_func()
            error_message = None
        except Exception as e:
            passed = False
            error_message = str(e)
        
        validation = CheckpointValidation(
            name=name,
            description=description,
            passed=passed,
            error_message=error_message,
            metadata=metadata or {},
        )
        
        checkpoint.validations.append(validation)
        self._save_checkpoints()
        
        return validation
    
    def evaluate_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """
        Evaluate checkpoint status based on validations.
        
        Args:
            checkpoint: Checkpoint to evaluate
            
        Returns:
            True if all validations passed, False otherwise
        """
        if not checkpoint.validations:
            checkpoint.status = CheckpointStatus.FAILED
            self._save_checkpoints()
            return False
        
        all_passed = all(v.passed for v in checkpoint.validations)
        
        if all_passed:
            checkpoint.status = CheckpointStatus.PASSED
        else:
            checkpoint.status = CheckpointStatus.FAILED
        
        self._save_checkpoints()
        return all_passed
    
    def mark_user_approved(self, checkpoint: Checkpoint) -> None:
        """
        Mark checkpoint as user-approved.
        
        Args:
            checkpoint: Checkpoint to approve
        """
        checkpoint.user_approved = True
        self._save_checkpoints()
    
    def can_proceed_to_next_phase(self, current_phase: str) -> bool:
        """
        Check if can proceed to next phase.
        
        Args:
            current_phase: Current phase name
            
        Returns:
            True if checkpoint passed and user approved, False otherwise
        """
        # Find checkpoint for current phase
        checkpoint = self.get_checkpoint_for_phase(current_phase)
        
        if not checkpoint:
            return False
        
        return (
            checkpoint.status == CheckpointStatus.PASSED and
            checkpoint.user_approved
        )
    
    def get_checkpoint_for_phase(self, phase: str) -> Optional[Checkpoint]:
        """
        Get checkpoint for specific phase.
        
        Args:
            phase: Phase name
            
        Returns:
            Checkpoint if found, None otherwise
        """
        for checkpoint in reversed(self.checkpoints):
            if checkpoint.phase == phase:
                return checkpoint
        return None
    
    def get_all_checkpoints(self) -> List[Checkpoint]:
        """Get all checkpoints"""
        return self.checkpoints.copy()
    
    def get_failed_validations(self, checkpoint: Checkpoint) -> List[CheckpointValidation]:
        """
        Get all failed validations for checkpoint.
        
        Args:
            checkpoint: Checkpoint to check
            
        Returns:
            List of failed validations
        """
        return [v for v in checkpoint.validations if not v.passed]
    
    def get_checkpoint_summary(self, checkpoint: Checkpoint) -> Dict:
        """
        Get summary of checkpoint.
        
        Args:
            checkpoint: Checkpoint to summarize
            
        Returns:
            Dictionary with checkpoint summary
        """
        total_validations = len(checkpoint.validations)
        passed_validations = sum(1 for v in checkpoint.validations if v.passed)
        failed_validations = total_validations - passed_validations
        
        return {
            'name': checkpoint.name,
            'phase': checkpoint.phase,
            'status': checkpoint.status.value,
            'user_approved': checkpoint.user_approved,
            'total_validations': total_validations,
            'passed_validations': passed_validations,
            'failed_validations': failed_validations,
            'can_proceed': checkpoint.status == CheckpointStatus.PASSED and checkpoint.user_approved,
            'failed_validation_details': [
                {
                    'name': v.name,
                    'description': v.description,
                    'error': v.error_message,
                }
                for v in checkpoint.validations if not v.passed
            ],
        }
    
    def _save_checkpoints(self) -> None:
        """Persist checkpoints to disk"""
        data = {
            'checkpoints': [c.to_dict() for c in self.checkpoints]
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_checkpoints(self) -> List[Checkpoint]:
        """Load checkpoints from disk"""
        with open(self.checkpoint_file, 'r') as f:
            data = json.load(f)
        
        return [Checkpoint.from_dict(c) for c in data['checkpoints']]
