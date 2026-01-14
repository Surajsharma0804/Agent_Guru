"""
Audit Orchestrator - Phase Management and Coordination

Coordinates all audit phases with strict safety enforcement.
Ensures no destructive changes occur without proof of safety.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import json


class AuditPhase(Enum):
    """Audit execution phases"""
    INITIALIZATION = "initialization"
    PHASE_1_ANALYSIS = "phase_1_analysis"
    PHASE_1_CHECKPOINT = "phase_1_checkpoint"
    PHASE_2_TRANSFORMATION = "phase_2_transformation"
    PHASE_2_CHECKPOINT = "phase_2_checkpoint"
    PHASE_3_CONSOLIDATION = "phase_3_consolidation"
    PHASE_3_CHECKPOINT = "phase_3_checkpoint"
    PHASE_4_VALIDATION = "phase_4_validation"
    PHASE_4_CHECKPOINT = "phase_4_checkpoint"
    COMPLETE = "complete"


@dataclass
class PhaseResult:
    """Result of a phase execution"""
    phase: AuditPhase
    success: bool
    start_time: datetime
    end_time: datetime
    files_analyzed: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class AuditState:
    """Current state of the audit process"""
    current_phase: AuditPhase
    phase_history: List[PhaseResult] = field(default_factory=list)
    security_files: Set[Path] = field(default_factory=set)
    immune_directories: Set[Path] = field(default_factory=set)
    modified_files: Set[Path] = field(default_factory=set)
    deleted_files: Set[Path] = field(default_factory=set)
    checkpoint_passed: bool = False
    
    def to_dict(self) -> Dict:
        """Serialize state to dictionary"""
        return {
            'current_phase': self.current_phase.value,
            'phase_history': [
                {
                    'phase': r.phase.value,
                    'success': r.success,
                    'start_time': r.start_time.isoformat(),
                    'end_time': r.end_time.isoformat(),
                    'files_analyzed': r.files_analyzed,
                    'files_modified': r.files_modified,
                    'files_deleted': r.files_deleted,
                    'errors': r.errors,
                    'warnings': r.warnings,
                    'metadata': r.metadata,
                }
                for r in self.phase_history
            ],
            'security_files': [str(f) for f in self.security_files],
            'immune_directories': [str(d) for d in self.immune_directories],
            'modified_files': [str(f) for f in self.modified_files],
            'deleted_files': [str(f) for f in self.deleted_files],
            'checkpoint_passed': self.checkpoint_passed,
        }


class AuditOrchestrator:
    """
    Orchestrates the complete audit process across all phases.
    
    Responsibilities:
    - Phase sequencing and validation
    - Safety enforcement (fail-closed on uncertainty)
    - State persistence and recovery
    - Security boundary protection
    """
    
    def __init__(self, workspace_root: Path, state_file: Optional[Path] = None):
        """
        Initialize audit orchestrator.
        
        Args:
            workspace_root: Root directory of the workspace
            state_file: Path to state persistence file (default: workspace_root/.audit_state.json)
        """
        self.workspace_root = workspace_root.resolve()
        self.state_file = state_file or (workspace_root / '.audit_state.json')
        
        # Initialize state
        if self.state_file.exists():
            self.state = self._load_state()
        else:
            self.state = AuditState(
                current_phase=AuditPhase.INITIALIZATION,
                immune_directories={
                    self.workspace_root / '.kiro',
                    self.workspace_root / '.git',
                }
            )
        
        # Phase transition rules
        self._phase_transitions = {
            AuditPhase.INITIALIZATION: AuditPhase.PHASE_1_ANALYSIS,
            AuditPhase.PHASE_1_ANALYSIS: AuditPhase.PHASE_1_CHECKPOINT,
            AuditPhase.PHASE_1_CHECKPOINT: AuditPhase.PHASE_2_TRANSFORMATION,
            AuditPhase.PHASE_2_TRANSFORMATION: AuditPhase.PHASE_2_CHECKPOINT,
            AuditPhase.PHASE_2_CHECKPOINT: AuditPhase.PHASE_3_CONSOLIDATION,
            AuditPhase.PHASE_3_CONSOLIDATION: AuditPhase.PHASE_3_CHECKPOINT,
            AuditPhase.PHASE_3_CHECKPOINT: AuditPhase.PHASE_4_VALIDATION,
            AuditPhase.PHASE_4_VALIDATION: AuditPhase.PHASE_4_CHECKPOINT,
            AuditPhase.PHASE_4_CHECKPOINT: AuditPhase.COMPLETE,
        }
    
    def get_current_phase(self) -> AuditPhase:
        """Get current audit phase"""
        return self.state.current_phase
    
    def can_transition_to(self, target_phase: AuditPhase) -> bool:
        """
        Check if transition to target phase is allowed.
        
        Args:
            target_phase: Target phase to transition to
            
        Returns:
            True if transition is allowed, False otherwise
        """
        expected_next = self._phase_transitions.get(self.state.current_phase)
        return target_phase == expected_next
    
    def start_phase(self, phase: AuditPhase) -> None:
        """
        Start a new phase.
        
        Args:
            phase: Phase to start
            
        Raises:
            ValueError: If phase transition is not allowed
        """
        if not self.can_transition_to(phase):
            raise ValueError(
                f"Cannot transition from {self.state.current_phase.value} to {phase.value}. "
                f"Expected: {self._phase_transitions.get(self.state.current_phase)}"
            )
        
        self.state.current_phase = phase
        self.state.checkpoint_passed = False
        self._save_state()
    
    def complete_phase(self, result: PhaseResult) -> None:
        """
        Complete current phase and record results.
        
        Args:
            result: Phase execution result
        """
        if result.phase != self.state.current_phase:
            raise ValueError(
                f"Phase mismatch: completing {result.phase.value} but current is {self.state.current_phase.value}"
            )
        
        self.state.phase_history.append(result)
        self._save_state()
    
    def mark_checkpoint_passed(self) -> None:
        """Mark current checkpoint as passed"""
        if not self.state.current_phase.value.endswith('checkpoint'):
            raise ValueError(f"Current phase {self.state.current_phase.value} is not a checkpoint")
        
        self.state.checkpoint_passed = True
        self._save_state()
    
    def is_file_immune(self, file_path: Path) -> bool:
        """
        Check if file is immune from modification/deletion.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file is immune, False otherwise
        """
        file_path = file_path.resolve()
        
        # Check if in immune directory
        for immune_dir in self.state.immune_directories:
            try:
                file_path.relative_to(immune_dir)
                return True
            except ValueError:
                continue
        
        return False
    
    def is_file_security_critical(self, file_path: Path) -> bool:
        """
        Check if file is security-critical.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file is security-critical, False otherwise
        """
        return file_path.resolve() in self.state.security_files
    
    def register_security_file(self, file_path: Path) -> None:
        """
        Register a file as security-critical.
        
        Args:
            file_path: Path to register
        """
        self.state.security_files.add(file_path.resolve())
        self._save_state()
    
    def register_file_modification(self, file_path: Path) -> None:
        """
        Register a file modification.
        
        Args:
            file_path: Path that was modified
        """
        self.state.modified_files.add(file_path.resolve())
        self._save_state()
    
    def register_file_deletion(self, file_path: Path) -> None:
        """
        Register a file deletion.
        
        Args:
            file_path: Path that was deleted
        """
        self.state.deleted_files.add(file_path.resolve())
        self._save_state()
    
    def get_phase_statistics(self) -> Dict:
        """
        Get statistics for all completed phases.
        
        Returns:
            Dictionary with phase statistics
        """
        stats = {
            'total_phases_completed': len(self.state.phase_history),
            'total_files_analyzed': sum(r.files_analyzed for r in self.state.phase_history),
            'total_files_modified': len(self.state.modified_files),
            'total_files_deleted': len(self.state.deleted_files),
            'total_errors': sum(len(r.errors) for r in self.state.phase_history),
            'total_warnings': sum(len(r.warnings) for r in self.state.phase_history),
            'phases': [
                {
                    'phase': r.phase.value,
                    'success': r.success,
                    'duration_seconds': (r.end_time - r.start_time).total_seconds(),
                    'files_analyzed': r.files_analyzed,
                    'files_modified': r.files_modified,
                    'files_deleted': r.files_deleted,
                }
                for r in self.state.phase_history
            ]
        }
        return stats
    
    def _save_state(self) -> None:
        """Persist current state to disk"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state.to_dict(), f, indent=2)
    
    def _load_state(self) -> AuditState:
        """Load state from disk"""
        with open(self.state_file, 'r') as f:
            data = json.load(f)
        
        state = AuditState(
            current_phase=AuditPhase(data['current_phase']),
            security_files={Path(f) for f in data['security_files']},
            immune_directories={Path(d) for d in data['immune_directories']},
            modified_files={Path(f) for f in data['modified_files']},
            deleted_files={Path(f) for f in data['deleted_files']},
            checkpoint_passed=data['checkpoint_passed'],
        )
        
        # Reconstruct phase history
        for r in data['phase_history']:
            state.phase_history.append(PhaseResult(
                phase=AuditPhase(r['phase']),
                success=r['success'],
                start_time=datetime.fromisoformat(r['start_time']),
                end_time=datetime.fromisoformat(r['end_time']),
                files_analyzed=r['files_analyzed'],
                files_modified=r['files_modified'],
                files_deleted=r['files_deleted'],
                errors=r['errors'],
                warnings=r['warnings'],
                metadata=r['metadata'],
            ))
        
        return state
