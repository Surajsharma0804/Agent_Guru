"""
Audit Log Integrity Verifier

Production-grade integrity verification system for audit logs.
Provides comprehensive verification of cryptographic signatures,
hash chain integrity, and tamper detection capabilities.

This verifier ensures the audit log maintains cryptographic integrity
and can detect any tampering attempts or corruption.
"""

import json
import hashlib
import hmac
import logging
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager

from .audit_logger import AuditLogEntry, IntegrityVerificationResult


class IntegrityVerifier:
    """
    Comprehensive audit log integrity verification system.
    
    This verifier provides:
    - Cryptographic signature verification for all entries
    - Hash chain integrity verification to detect tampering
    - Sequence number validation to detect insertion/deletion
    - Comprehensive tamper detection and reporting
    - Forensic analysis capabilities for security incidents
    - Performance-optimized verification for large audit logs
    
    Security Features:
    - Verifies HMAC-SHA256 signatures for all entries
    - Validates hash chain linking to detect modifications
    - Checks sequence number continuity for completeness
    - Detects insertion, deletion, and modification attempts
    - Provides detailed forensic information for investigations
    """
    
    def __init__(self, db_path: str, signing_key: bytes):
        """
        Initialize integrity verifier.
        
        Args:
            db_path: Path to audit log database
            signing_key: Cryptographic signing key for verification
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = Path(db_path)
        self.signing_key = signing_key
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"Audit database not found: {db_path}")
    
    @contextmanager
    def _get_db_connection(self):
        """Get database connection for verification"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            yield conn
        finally:
            conn.close()
    
    def _calculate_entry_hash(self, entry_data: Dict[str, Any]) -> str:
        """Calculate expected hash for an audit entry"""
        hash_data = {
            "id": entry_data["id"],
            "timestamp": entry_data["timestamp"],
            "sequence_number": entry_data["sequence_number"],
            "event_type": entry_data["event_type"],
            "component": entry_data["component"],
            "action": entry_data["action"],
            "details": entry_data["details"],
            "previous_hash": entry_data["previous_hash"]
        }
        
        canonical_json = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    
    def _verify_signature(self, entry_hash: str, signature: str) -> bool:
        """Verify HMAC-SHA256 signature for an entry"""
        expected_signature = hmac.new(
            self.signing_key,
            entry_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def verify_single_entry(self, entry_data: Tuple) -> Dict[str, Any]:
        """
        Verify integrity of a single audit entry.
        
        Args:
            entry_data: Database row tuple for the entry
            
        Returns:
            Dictionary with verification results
        """
        try:
            # Unpack entry data
            (entry_id, timestamp, sequence_number, event_type, severity,
             component, action, details_json, session_id, user_id,
             device_id, correlation_id, previous_hash, entry_hash, signature) = entry_data
            
            # Parse details
            try:
                details = json.loads(details_json)
            except json.JSONDecodeError as e:
                return {
                    "entry_id": entry_id,
                    "valid": False,
                    "errors": [f"Invalid JSON in details: {e}"]
                }
            
            # Reconstruct entry data for verification
            verify_data = {
                "id": entry_id,
                "timestamp": timestamp,
                "sequence_number": sequence_number,
                "event_type": event_type,
                "component": component,
                "action": action,
                "details": details,
                "previous_hash": previous_hash
            }
            
            errors = []
            
            # Verify entry hash
            expected_hash = self._calculate_entry_hash(verify_data)
            if expected_hash != entry_hash:
                errors.append(f"Hash mismatch: expected {expected_hash}, got {entry_hash}")
            
            # Verify signature
            if not self._verify_signature(entry_hash, signature):
                errors.append("Invalid HMAC signature")
            
            # Validate timestamp format
            try:
                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                errors.append(f"Invalid timestamp format: {timestamp}")
            
            # Validate sequence number
            if not isinstance(sequence_number, int) or sequence_number < 1:
                errors.append(f"Invalid sequence number: {sequence_number}")
            
            return {
                "entry_id": entry_id,
                "sequence_number": sequence_number,
                "valid": len(errors) == 0,
                "errors": errors,
                "timestamp": timestamp,
                "event_type": event_type,
                "component": component,
                "action": action
            }
            
        except Exception as e:
            return {
                "entry_id": entry_data[0] if len(entry_data) > 0 else "unknown",
                "valid": False,
                "errors": [f"Verification exception: {e}"]
            }
    
    def verify_hash_chain(self, entries: List[Tuple], start_sequence: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify hash chain integrity across all entries.
        
        CRITICAL SECURITY FIX: Proper hash chain verification logic
        that correctly handles partial chain verification when examining
        a subset of entries starting from a specific sequence number.
        
        Args:
            entries: List of database row tuples sorted by sequence number
            start_sequence: If provided, indicates this is a partial chain starting from this sequence
            
        Returns:
            Dictionary with hash chain verification results
        """
        if not entries:
            return {
                "valid": True,
                "total_entries": 0,
                "chain_breaks": []
            }
        
        chain_breaks = []
        
        # CRITICAL FIX: Handle partial chain verification correctly
        if start_sequence is not None and start_sequence > 1:
            # For partial chains starting after sequence 1, we need to get the previous entry's hash
            # to properly validate the chain continuity
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.execute(
                        "SELECT entry_hash FROM audit_entries WHERE sequence_number = ? ORDER BY sequence_number",
                        (start_sequence - 1,)
                    )
                    prev_result = cursor.fetchone()
                    expected_previous_hash = prev_result[0] if prev_result else None
            except Exception as e:
                self.logger.error(f"Failed to get previous hash for partial chain verification: {e}")
                expected_previous_hash = None
        else:
            # For complete chains or chains starting from sequence 1
            expected_previous_hash = None  # First entry should have None as previous_hash
        
        for i, entry_data in enumerate(entries):
            entry_id = entry_data[0]
            sequence_number = entry_data[2]
            stored_previous_hash = entry_data[12]  # previous_hash column
            entry_hash = entry_data[13]  # entry_hash column
            
            # CRITICAL FIX: Proper hash chain verification
            # For the first entry in a complete chain (sequence 1), both expected and stored should be None
            # For partial chains, the first entry should match the previous entry's hash
            # For subsequent entries, stored should match the previous entry's hash
            if stored_previous_hash != expected_previous_hash:
                chain_breaks.append({
                    "entry_id": entry_id,
                    "sequence_number": sequence_number,
                    "expected_previous_hash": expected_previous_hash,
                    "actual_previous_hash": stored_previous_hash,
                    "position": i
                })
            
            # Set up expected previous hash for next iteration
            expected_previous_hash = entry_hash
        
        return {
            "valid": len(chain_breaks) == 0,
            "total_entries": len(entries),
            "chain_breaks": chain_breaks
        }
    
    def verify_sequence_continuity(self, entries: List[Tuple], start_sequence: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify sequence number continuity to detect missing entries.
        
        CRITICAL SECURITY FIX: Handle partial chain verification correctly
        by starting sequence validation from the appropriate sequence number.
        
        Args:
            entries: List of database row tuples sorted by sequence number
            start_sequence: If provided, indicates this is a partial chain starting from this sequence
            
        Returns:
            Dictionary with sequence verification results
        """
        if not entries:
            return {
                "valid": True,
                "total_entries": 0,
                "sequence_gaps": [],
                "duplicate_sequences": []
            }
        
        sequence_gaps = []
        duplicate_sequences = []
        seen_sequences = set()
        
        # CRITICAL FIX: For partial chain verification, start from the first entry's sequence number
        # For complete chain verification, start from 1
        if start_sequence is not None:
            expected_sequence = start_sequence
        else:
            # For complete chains, start from the first entry's sequence number
            # This handles cases where the audit log doesn't start from sequence 1
            expected_sequence = entries[0][2] if entries else 1
        
        for entry_data in entries:
            entry_id = entry_data[0]
            sequence_number = entry_data[2]
            
            # Check for duplicates
            if sequence_number in seen_sequences:
                duplicate_sequences.append({
                    "entry_id": entry_id,
                    "sequence_number": sequence_number
                })
            else:
                seen_sequences.add(sequence_number)
            
            # Check for gaps
            if sequence_number != expected_sequence:
                if sequence_number > expected_sequence:
                    # Gap detected
                    sequence_gaps.append({
                        "expected": expected_sequence,
                        "actual": sequence_number,
                        "gap_size": sequence_number - expected_sequence,
                        "entry_id": entry_id
                    })
                    expected_sequence = sequence_number + 1
                else:
                    # Out of order (should not happen with proper sorting)
                    sequence_gaps.append({
                        "expected": expected_sequence,
                        "actual": sequence_number,
                        "error": "out_of_order",
                        "entry_id": entry_id
                    })
            else:
                expected_sequence += 1
        
        return {
            "valid": len(sequence_gaps) == 0 and len(duplicate_sequences) == 0,
            "total_entries": len(entries),
            "sequence_gaps": sequence_gaps,
            "duplicate_sequences": duplicate_sequences,
            "highest_sequence": entries[-1][2] if entries else 0
        }
    
    def verify_complete_integrity(self, 
                                 max_entries: Optional[int] = None,
                                 start_sequence: Optional[int] = None,
                                 end_sequence: Optional[int] = None) -> IntegrityVerificationResult:
        """
        Perform comprehensive integrity verification of audit log.
        
        Args:
            max_entries: Maximum number of entries to verify (None for all)
            start_sequence: Starting sequence number for verification
            end_sequence: Ending sequence number for verification
            
        Returns:
            Comprehensive integrity verification result
        """
        verification_start = datetime.now(timezone.utc)
        
        try:
            with self._get_db_connection() as conn:
                # Build query with optional constraints
                query = """
                    SELECT id, timestamp, sequence_number, event_type, severity,
                           component, action, details, session_id, user_id,
                           device_id, correlation_id, previous_hash, entry_hash, signature
                    FROM audit_entries
                """
                
                params = []
                conditions = []
                
                if start_sequence is not None:
                    conditions.append("sequence_number >= ?")
                    params.append(start_sequence)
                
                if end_sequence is not None:
                    conditions.append("sequence_number <= ?")
                    params.append(end_sequence)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY sequence_number"
                
                if max_entries is not None:
                    query += " LIMIT ?"
                    params.append(max_entries)
                
                cursor = conn.execute(query, params)
                entries = cursor.fetchall()
                
                if not entries:
                    return IntegrityVerificationResult(
                        verified=True,
                        total_entries=0,
                        hash_chain_valid=True,
                        signatures_valid=True,
                        sequence_valid=True,
                        invalid_entries=[],
                        verification_timestamp=verification_start.isoformat(),
                        error_message=None
                    )
                
                # Verify individual entries
                invalid_entries = []
                signatures_valid = True
                
                self.logger.info(f"Verifying {len(entries)} audit entries...")
                
                for entry_data in entries:
                    entry_result = self.verify_single_entry(entry_data)
                    if not entry_result["valid"]:
                        invalid_entries.append(entry_result)
                        signatures_valid = False
                
                # Verify hash chain
                chain_result = self.verify_hash_chain(entries, start_sequence)
                hash_chain_valid = chain_result["valid"]
                
                if not hash_chain_valid:
                    for break_info in chain_result["chain_breaks"]:
                        invalid_entries.append({
                            "entry_id": break_info["entry_id"],
                            "sequence_number": break_info["sequence_number"],
                            "valid": False,
                            "errors": ["Hash chain break"],
                            "chain_break_details": break_info
                        })
                
                # Verify sequence continuity
                sequence_result = self.verify_sequence_continuity(entries, start_sequence)
                sequence_valid = sequence_result["valid"]
                
                if not sequence_valid:
                    for gap_info in sequence_result["sequence_gaps"]:
                        invalid_entries.append({
                            "entry_id": gap_info.get("entry_id", "unknown"),
                            "sequence_number": gap_info.get("actual", "unknown"),
                            "valid": False,
                            "errors": ["Sequence gap or duplication"],
                            "sequence_gap_details": gap_info
                        })
                
                # Overall verification result
                verified = signatures_valid and hash_chain_valid and sequence_valid
                
                verification_end = datetime.now(timezone.utc)
                verification_time = (verification_end - verification_start).total_seconds()
                
                self.logger.info(f"Integrity verification completed in {verification_time:.2f}s")
                self.logger.info(f"Verified: {verified}, Entries: {len(entries)}, Invalid: {len(invalid_entries)}")
                
                return IntegrityVerificationResult(
                    verified=verified,
                    total_entries=len(entries),
                    hash_chain_valid=hash_chain_valid,
                    signatures_valid=signatures_valid,
                    sequence_valid=sequence_valid,
                    invalid_entries=invalid_entries,
                    verification_timestamp=verification_end.isoformat(),
                    error_message=None
                )
                
        except Exception as e:
            error_msg = f"Integrity verification failed: {e}"
            self.logger.error(error_msg)
            
            return IntegrityVerificationResult(
                verified=False,
                total_entries=0,
                hash_chain_valid=False,
                signatures_valid=False,
                sequence_valid=False,
                invalid_entries=[],
                verification_timestamp=datetime.now(timezone.utc).isoformat(),
                error_message=error_msg
            )
    
    def verify_recent_entries(self, count: int = 100) -> IntegrityVerificationResult:
        """
        Verify integrity of recent audit entries for real-time monitoring.
        
        Args:
            count: Number of recent entries to verify
            
        Returns:
            Integrity verification result for recent entries
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT sequence_number FROM audit_entries 
                    ORDER BY sequence_number DESC LIMIT 1
                """)
                
                row = cursor.fetchone()
                if not row:
                    # No entries to verify
                    return IntegrityVerificationResult(
                        verified=True,
                        total_entries=0,
                        hash_chain_valid=True,
                        signatures_valid=True,
                        sequence_valid=True,
                        invalid_entries=[],
                        verification_timestamp=datetime.now(timezone.utc).isoformat()
                    )
                
                highest_sequence = row[0]
                start_sequence = max(1, highest_sequence - count + 1)
                
                return self.verify_complete_integrity(
                    start_sequence=start_sequence,
                    end_sequence=highest_sequence
                )
                
        except Exception as e:
            error_msg = f"Recent entries verification failed: {e}"
            self.logger.error(error_msg)
            
            return IntegrityVerificationResult(
                verified=False,
                total_entries=0,
                hash_chain_valid=False,
                signatures_valid=False,
                sequence_valid=False,
                invalid_entries=[],
                verification_timestamp=datetime.now(timezone.utc).isoformat(),
                error_message=error_msg
            )
    
    def get_verification_statistics(self) -> Dict[str, Any]:
        """Get statistics about audit log for verification planning"""
        try:
            with self._get_db_connection() as conn:
                # Get total entries
                cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
                total_entries = cursor.fetchone()[0]
                
                # Get sequence range
                cursor = conn.execute("""
                    SELECT MIN(sequence_number), MAX(sequence_number) 
                    FROM audit_entries
                """)
                seq_range = cursor.fetchone()
                min_seq, max_seq = seq_range if seq_range[0] is not None else (None, None)
                
                # Get date range
                cursor = conn.execute("""
                    SELECT MIN(timestamp), MAX(timestamp) 
                    FROM audit_entries
                """)
                date_range = cursor.fetchone()
                min_date, max_date = date_range if date_range[0] is not None else (None, None)
                
                # Get database size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                
                return {
                    "database_path": str(self.db_path),
                    "total_entries": total_entries,
                    "sequence_range": {
                        "min": min_seq,
                        "max": max_seq,
                        "expected_count": max_seq - min_seq + 1 if min_seq and max_seq else 0
                    },
                    "date_range": {
                        "earliest": min_date,
                        "latest": max_date
                    },
                    "database_size_bytes": db_size,
                    "has_signing_key": self.signing_key is not None
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get verification statistics: {e}")
            return {"error": str(e)}