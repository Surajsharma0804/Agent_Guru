"""
File System Utilities - Safe File Operations with Rollback

Provides safe file operations with automatic rollback on failure.
All operations are logged and can be reverted.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import shutil
import hashlib


class FileOperationType(Enum):
    """Types of file operations"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    RENAME = "rename"
    COPY = "copy"


@dataclass
class FileOperation:
    """Record of a file operation"""
    operation_type: FileOperationType
    target_path: Path
    timestamp: datetime
    success: bool
    backup_path: Optional[Path] = None
    original_content_hash: Optional[str] = None
    new_content_hash: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class OperationResult:
    """Result of a file operation"""
    success: bool
    operation: FileOperation
    error_message: Optional[str] = None


class FileSystemUtils:
    """
    Safe file system operations with rollback capability.
    
    All destructive operations create backups and can be reverted.
    Operations are logged for audit trail.
    """
    
    def __init__(self, backup_dir: Path):
        """
        Initialize file system utilities.
        
        Args:
            backup_dir: Directory for storing backups
        """
        self.backup_dir = backup_dir.resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.operation_log: List[FileOperation] = []
    
    def read_file_complete(self, file_path: Path) -> OperationResult:
        """
        Read complete file content without truncation.
        
        Args:
            file_path: Path to file
            
        Returns:
            OperationResult with file content in metadata['content']
        """
        file_path = file_path.resolve()
        operation = FileOperation(
            operation_type=FileOperationType.READ,
            target_path=file_path,
            timestamp=datetime.now(),
            success=False,
        )
        
        try:
            # Detect encoding
            with open(file_path, 'rb') as f:
                raw_content = f.read()
            
            # Try UTF-8 first, fall back to latin-1
            try:
                content = raw_content.decode('utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                content = raw_content.decode('latin-1')
                encoding = 'latin-1'
            
            # Calculate hash
            content_hash = hashlib.sha256(raw_content).hexdigest()
            
            # Count lines
            line_count = content.count('\n')
            if content and not content.endswith('\n'):
                line_count += 1
            
            operation.success = True
            operation.original_content_hash = content_hash
            operation.metadata = {
                'content': content,
                'encoding': encoding,
                'line_count': line_count,
                'byte_size': len(raw_content),
            }
            
            self.operation_log.append(operation)
            return OperationResult(success=True, operation=operation)
            
        except Exception as e:
            operation.error_message = str(e)
            self.operation_log.append(operation)
            return OperationResult(
                success=False,
                operation=operation,
                error_message=str(e)
            )
    
    def write_file_safe(self, file_path: Path, content: str, create_backup: bool = True) -> OperationResult:
        """
        Write file with automatic backup.
        
        Args:
            file_path: Path to file
            content: Content to write
            create_backup: Whether to create backup of existing file
            
        Returns:
            OperationResult
        """
        file_path = file_path.resolve()
        operation = FileOperation(
            operation_type=FileOperationType.WRITE,
            target_path=file_path,
            timestamp=datetime.now(),
            success=False,
        )
        
        try:
            # Create backup if file exists
            backup_path = None
            if file_path.exists() and create_backup:
                backup_path = self._create_backup(file_path)
                operation.backup_path = backup_path
                
                # Store original hash
                with open(file_path, 'rb') as f:
                    operation.original_content_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Write new content
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Calculate new hash
            with open(file_path, 'rb') as f:
                operation.new_content_hash = hashlib.sha256(f.read()).hexdigest()
            
            operation.success = True
            self.operation_log.append(operation)
            return OperationResult(success=True, operation=operation)
            
        except Exception as e:
            # Restore backup if write failed
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
            
            operation.error_message = str(e)
            self.operation_log.append(operation)
            return OperationResult(
                success=False,
                operation=operation,
                error_message=str(e)
            )
    
    def delete_file_safe(self, file_path: Path, create_backup: bool = True) -> OperationResult:
        """
        Delete file with automatic backup.
        
        Args:
            file_path: Path to file
            create_backup: Whether to create backup before deletion
            
        Returns:
            OperationResult
        """
        file_path = file_path.resolve()
        operation = FileOperation(
            operation_type=FileOperationType.DELETE,
            target_path=file_path,
            timestamp=datetime.now(),
            success=False,
        )
        
        try:
            if not file_path.exists():
                operation.error_message = "File does not exist"
                self.operation_log.append(operation)
                return OperationResult(
                    success=False,
                    operation=operation,
                    error_message="File does not exist"
                )
            
            # Create backup
            if create_backup:
                backup_path = self._create_backup(file_path)
                operation.backup_path = backup_path
                
                # Store original hash
                with open(file_path, 'rb') as f:
                    operation.original_content_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Delete file
            file_path.unlink()
            
            operation.success = True
            self.operation_log.append(operation)
            return OperationResult(success=True, operation=operation)
            
        except Exception as e:
            operation.error_message = str(e)
            self.operation_log.append(operation)
            return OperationResult(
                success=False,
                operation=operation,
                error_message=str(e)
            )
    
    def rename_file_safe(self, old_path: Path, new_path: Path, create_backup: bool = True) -> OperationResult:
        """
        Rename file with automatic backup.
        
        Args:
            old_path: Current file path
            new_path: New file path
            create_backup: Whether to create backup before rename
            
        Returns:
            OperationResult
        """
        old_path = old_path.resolve()
        new_path = new_path.resolve()
        
        operation = FileOperation(
            operation_type=FileOperationType.RENAME,
            target_path=old_path,
            timestamp=datetime.now(),
            success=False,
            metadata={'new_path': str(new_path)},
        )
        
        try:
            if not old_path.exists():
                operation.error_message = "Source file does not exist"
                self.operation_log.append(operation)
                return OperationResult(
                    success=False,
                    operation=operation,
                    error_message="Source file does not exist"
                )
            
            if new_path.exists():
                operation.error_message = "Destination file already exists"
                self.operation_log.append(operation)
                return OperationResult(
                    success=False,
                    operation=operation,
                    error_message="Destination file already exists"
                )
            
            # Create backup
            if create_backup:
                backup_path = self._create_backup(old_path)
                operation.backup_path = backup_path
                
                # Store original hash
                with open(old_path, 'rb') as f:
                    operation.original_content_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Rename file
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)
            
            # Verify new file
            with open(new_path, 'rb') as f:
                operation.new_content_hash = hashlib.sha256(f.read()).hexdigest()
            
            operation.success = True
            self.operation_log.append(operation)
            return OperationResult(success=True, operation=operation)
            
        except Exception as e:
            operation.error_message = str(e)
            self.operation_log.append(operation)
            return OperationResult(
                success=False,
                operation=operation,
                error_message=str(e)
            )
    
    def rollback_operation(self, operation: FileOperation) -> bool:
        """
        Rollback a file operation.
        
        Args:
            operation: Operation to rollback
            
        Returns:
            True if rollback successful, False otherwise
        """
        try:
            if not operation.success:
                return True  # Nothing to rollback
            
            if operation.backup_path and operation.backup_path.exists():
                if operation.operation_type == FileOperationType.DELETE:
                    # Restore deleted file
                    shutil.copy2(operation.backup_path, operation.target_path)
                    return True
                    
                elif operation.operation_type == FileOperationType.WRITE:
                    # Restore original content
                    shutil.copy2(operation.backup_path, operation.target_path)
                    return True
                    
                elif operation.operation_type == FileOperationType.RENAME:
                    # Restore original name
                    new_path = Path(operation.metadata['new_path'])
                    if new_path.exists():
                        new_path.rename(operation.target_path)
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _create_backup(self, file_path: Path) -> Path:
        """
        Create backup of file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        backup_name = f"{file_path.name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def get_operation_log(self) -> List[FileOperation]:
        """Get complete operation log"""
        return self.operation_log.copy()
    
    def get_successful_operations(self) -> List[FileOperation]:
        """Get all successful operations"""
        return [op for op in self.operation_log if op.success]
    
    def get_failed_operations(self) -> List[FileOperation]:
        """Get all failed operations"""
        return [op for op in self.operation_log if not op.success]
