"""
Resource Monitoring and Sandbox Monitoring

Provides comprehensive monitoring of skill execution including:
- CPU, memory, disk, and network usage tracking
- Process monitoring and child process detection
- File handle and system resource tracking
- Sandbox escape detection through behavioral analysis
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import psutil

from .manifest import ResourceLimits


@dataclass
class ResourceUsage:
    """Snapshot of resource usage at a point in time."""
    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    disk_read_mb: float
    disk_write_mb: float
    network_sent_kb: float
    network_recv_kb: float
    file_handles: int
    child_processes: int
    
    def exceeds_limits(self, limits: ResourceLimits) -> Optional[str]:
        """Check if usage exceeds any limits. Returns violation type or None."""
        if self.cpu_percent > limits.max_cpu_percent:
            return f"cpu_percent ({self.cpu_percent:.1f}% > {limits.max_cpu_percent}%)"
        
        if self.memory_mb > limits.max_memory_mb:
            return f"memory ({self.memory_mb:.1f}MB > {limits.max_memory_mb}MB)"
        
        total_disk_mb = self.disk_read_mb + self.disk_write_mb
        if total_disk_mb > limits.max_disk_mb:
            return f"disk_io ({total_disk_mb:.1f}MB > {limits.max_disk_mb}MB)"
        
        total_network_kb = self.network_sent_kb + self.network_recv_kb
        if total_network_kb > limits.max_network_kb:
            return f"network_io ({total_network_kb:.1f}KB > {limits.max_network_kb}KB)"
        
        if self.file_handles > limits.max_file_handles:
            return f"file_handles ({self.file_handles} > {limits.max_file_handles})"
        
        if self.child_processes > limits.max_processes:
            return f"child_processes ({self.child_processes} > {limits.max_processes})"
        
        return None


@dataclass
class SandboxViolation:
    """Detected sandbox violation."""
    timestamp: datetime
    violation_type: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    process_info: Dict[str, Any]


class ResourceMonitor:
    """Monitors resource usage of a process and its children."""
    
    def __init__(self, process_id: int, limits: ResourceLimits, 
                 violation_callback: Optional[Callable[[str, ResourceUsage], None]] = None):
        self.process_id = process_id
        self.limits = limits
        self.violation_callback = violation_callback
        self.logger = logging.getLogger(__name__)
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._usage_history: List[ResourceUsage] = []
        self._start_time = datetime.now()
        
        # Initial resource counters
        self._initial_disk_io: Optional[Dict[str, int]] = None
        self._initial_network_io: Optional[Dict[str, int]] = None
    
    def start_monitoring(self, interval_seconds: float = 1.0) -> None:
        """Start monitoring process resources."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        self.logger.info(f"Started resource monitoring for process {self.process_id}")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring process resources."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        self.logger.info(f"Stopped resource monitoring for process {self.process_id}")
    
    def get_current_usage(self) -> Optional[ResourceUsage]:
        """Get current resource usage snapshot."""
        try:
            process = psutil.Process(self.process_id)
            if not process.is_running():
                return None
            
            # Get process and children
            children = process.children(recursive=True)
            all_processes = [process] + children
            
            # Aggregate CPU and memory
            total_cpu = sum(p.cpu_percent() for p in all_processes if p.is_running())
            total_memory_mb = sum(p.memory_info().rss for p in all_processes if p.is_running()) / (1024 * 1024)
            
            # Get I/O counters
            disk_read_mb = 0
            disk_write_mb = 0
            network_sent_kb = 0
            network_recv_kb = 0
            
            for p in all_processes:
                if not p.is_running():
                    continue
                
                try:
                    io_counters = p.io_counters()
                    disk_read_mb += io_counters.read_bytes / (1024 * 1024)
                    disk_write_mb += io_counters.write_bytes / (1024 * 1024)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
            
            # Network I/O is system-wide, so we approximate based on process activity
            try:
                net_io = psutil.net_io_counters()
                if self._initial_network_io is None:
                    self._initial_network_io = {
                        'sent': net_io.bytes_sent,
                        'recv': net_io.bytes_recv
                    }
                else:
                    network_sent_kb = (net_io.bytes_sent - self._initial_network_io['sent']) / 1024
                    network_recv_kb = (net_io.bytes_recv - self._initial_network_io['recv']) / 1024
            except Exception:
                pass
            
            # Count file handles and child processes
            file_handles = sum(len(p.open_files()) for p in all_processes if p.is_running())
            child_processes = len(children)
            
            return ResourceUsage(
                timestamp=datetime.now(),
                cpu_percent=total_cpu,
                memory_mb=total_memory_mb,
                disk_read_mb=disk_read_mb,
                disk_write_mb=disk_write_mb,
                network_sent_kb=network_sent_kb,
                network_recv_kb=network_recv_kb,
                file_handles=file_handles,
                child_processes=child_processes
            )
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.logger.warning(f"Failed to get resource usage for process {self.process_id}: {e}")
            return None
    
    def _monitor_loop(self, interval_seconds: float) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                usage = self.get_current_usage()
                if usage is None:
                    # Process no longer exists
                    break
                
                self._usage_history.append(usage)
                
                # Check for limit violations
                violation = usage.exceeds_limits(self.limits)
                if violation and self.violation_callback:
                    self.violation_callback(violation, usage)
                
                # Check execution time limit
                elapsed = datetime.now() - self._start_time
                if elapsed.total_seconds() > self.limits.max_execution_time_seconds:
                    if self.violation_callback:
                        self.violation_callback(
                            f"execution_time ({elapsed.total_seconds():.1f}s > {self.limits.max_execution_time_seconds}s)",
                            usage
                        )
                
                # Keep history manageable (last 100 entries)
                if len(self._usage_history) > 100:
                    self._usage_history = self._usage_history[-100:]
                
                time.sleep(interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Error in resource monitoring loop: {e}")
                time.sleep(interval_seconds)
    
    def get_usage_history(self) -> List[ResourceUsage]:
        """Get historical resource usage data."""
        return self._usage_history.copy()
    
    def get_peak_usage(self) -> Optional[ResourceUsage]:
        """Get peak resource usage across all metrics."""
        if not self._usage_history:
            return None
        
        # Find peak values across all metrics
        peak_cpu = max(self._usage_history, key=lambda u: u.cpu_percent)
        peak_memory = max(self._usage_history, key=lambda u: u.memory_mb)
        peak_disk = max(self._usage_history, key=lambda u: u.disk_read_mb + u.disk_write_mb)
        peak_network = max(self._usage_history, key=lambda u: u.network_sent_kb + u.network_recv_kb)
        
        # Create composite peak usage
        return ResourceUsage(
            timestamp=datetime.now(),
            cpu_percent=peak_cpu.cpu_percent,
            memory_mb=peak_memory.memory_mb,
            disk_read_mb=peak_disk.disk_read_mb,
            disk_write_mb=peak_disk.disk_write_mb,
            network_sent_kb=peak_network.network_sent_kb,
            network_recv_kb=peak_network.network_recv_kb,
            file_handles=max(u.file_handles for u in self._usage_history),
            child_processes=max(u.child_processes for u in self._usage_history)
        )


class SandboxMonitor:
    """Monitors for sandbox escape attempts and suspicious behavior."""
    
    def __init__(self, process_id: int, allowed_paths: List[str], 
                 violation_callback: Optional[Callable[[SandboxViolation], None]] = None):
        self.process_id = process_id
        self.allowed_paths = [Path(p).resolve() for p in allowed_paths]
        self.violation_callback = violation_callback
        self.logger = logging.getLogger(__name__)
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._violations: List[SandboxViolation] = []
        
        # Behavioral tracking
        self._file_access_attempts: Dict[str, int] = {}
        self._network_connections: List[Dict[str, Any]] = []
        self._process_creation_attempts: int = 0
    
    def start_monitoring(self, interval_seconds: float = 0.5) -> None:
        """Start monitoring for sandbox violations."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        self.logger.info(f"Started sandbox monitoring for process {self.process_id}")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring for sandbox violations."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        self.logger.info(f"Stopped sandbox monitoring for process {self.process_id}")
    
    def _monitor_loop(self, interval_seconds: float) -> None:
        """Main sandbox monitoring loop."""
        while self._monitoring:
            try:
                self._check_file_access_violations()
                self._check_network_violations()
                self._check_process_violations()
                self._check_system_call_violations()
                
                time.sleep(interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Error in sandbox monitoring loop: {e}")
                time.sleep(interval_seconds)
    
    def _check_file_access_violations(self) -> None:
        """Check for unauthorized file access attempts."""
        try:
            process = psutil.Process(self.process_id)
            if not process.is_running():
                return
            
            # Check open files for all processes in the tree
            children = process.children(recursive=True)
            all_processes = [process] + children
            
            for p in all_processes:
                if not p.is_running():
                    continue
                
                try:
                    open_files = p.open_files()
                    for file_info in open_files:
                        file_path = Path(file_info.path).resolve()
                        
                        # Check if file access is allowed
                        if not self._is_path_allowed(file_path):
                            self._record_violation(
                                violation_type="unauthorized_file_access",
                                description=f"Process {p.pid} accessed unauthorized file: {file_path}",
                                severity="high",
                                process_info={
                                    'pid': p.pid,
                                    'name': p.name(),
                                    'file_path': str(file_path),
                                    'file_mode': file_info.mode
                                }
                            )
                            
                            # Track repeated attempts
                            path_str = str(file_path)
                            self._file_access_attempts[path_str] = self._file_access_attempts.get(path_str, 0) + 1
                            
                            if self._file_access_attempts[path_str] > 3:
                                self._record_violation(
                                    violation_type="repeated_unauthorized_access",
                                    description=f"Repeated unauthorized access to {file_path} ({self._file_access_attempts[path_str]} attempts)",
                                    severity="critical",
                                    process_info={'pid': p.pid, 'name': p.name(), 'file_path': path_str}
                                )
                
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    def _check_network_violations(self) -> None:
        """Check for unauthorized network connections."""
        try:
            process = psutil.Process(self.process_id)
            if not process.is_running():
                return
            
            children = process.children(recursive=True)
            all_processes = [process] + children
            
            for p in all_processes:
                if not p.is_running():
                    continue
                
                try:
                    connections = p.connections()
                    for conn in connections:
                        if conn.status == psutil.CONN_ESTABLISHED:
                            # Record network connection for analysis
                            conn_info = {
                                'pid': p.pid,
                                'local_addr': conn.laddr,
                                'remote_addr': conn.raddr,
                                'status': conn.status,
                                'timestamp': datetime.now()
                            }
                            self._network_connections.append(conn_info)
                            
                            # Check for suspicious connections
                            if self._is_suspicious_connection(conn):
                                self._record_violation(
                                    violation_type="suspicious_network_connection",
                                    description=f"Process {p.pid} established suspicious connection to {conn.raddr}",
                                    severity="medium",
                                    process_info=conn_info
                                )
                
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    def _check_process_violations(self) -> None:
        """Check for unauthorized process creation."""
        try:
            process = psutil.Process(self.process_id)
            if not process.is_running():
                return
            
            children = process.children(recursive=True)
            current_child_count = len(children)
            
            # Track process creation attempts
            if current_child_count > self._process_creation_attempts:
                new_processes = current_child_count - self._process_creation_attempts
                self._process_creation_attempts = current_child_count
                
                # Check for excessive process creation
                if current_child_count > 5:  # Arbitrary threshold
                    self._record_violation(
                        violation_type="excessive_process_creation",
                        description=f"Process created {current_child_count} child processes",
                        severity="medium",
                        process_info={
                            'parent_pid': self.process_id,
                            'child_count': current_child_count,
                            'new_processes': new_processes
                        }
                    )
                
                # Check for suspicious process names
                for child in children:
                    if child.is_running():
                        try:
                            name = child.name().lower()
                            if any(suspicious in name for suspicious in ['cmd', 'powershell', 'bash', 'sh']):
                                self._record_violation(
                                    violation_type="suspicious_process_creation",
                                    description=f"Created suspicious child process: {name} (PID: {child.pid})",
                                    severity="high",
                                    process_info={
                                        'parent_pid': self.process_id,
                                        'child_pid': child.pid,
                                        'child_name': name
                                    }
                                )
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    def _check_system_call_violations(self) -> None:
        """Check for suspicious system calls (basic heuristics)."""
        # This is a simplified implementation - in production, you might use
        # more sophisticated system call monitoring tools
        try:
            process = psutil.Process(self.process_id)
            if not process.is_running():
                return
            
            # Check for suspicious process behavior patterns
            children = process.children(recursive=True)
            all_processes = [process] + children
            
            for p in all_processes:
                if not p.is_running():
                    continue
                
                try:
                    # Check for processes with suspicious command lines
                    cmdline = ' '.join(p.cmdline()).lower()
                    
                    suspicious_patterns = [
                        'reg add', 'reg delete', 'reg query',  # Registry manipulation
                        'net user', 'net localgroup',          # User management
                        'schtasks', 'at ',                     # Task scheduling
                        'wmic', 'powershell -enc',             # Encoded commands
                        'certutil -decode', 'bitsadmin'        # File download/decode
                    ]
                    
                    for pattern in suspicious_patterns:
                        if pattern in cmdline:
                            self._record_violation(
                                violation_type="suspicious_command_execution",
                                description=f"Process {p.pid} executed suspicious command: {pattern}",
                                severity="high",
                                process_info={
                                    'pid': p.pid,
                                    'name': p.name(),
                                    'cmdline': cmdline,
                                    'pattern': pattern
                                }
                            )
                            break
                
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if file path is within allowed directories."""
        try:
            for allowed_path in self.allowed_paths:
                path.relative_to(allowed_path)
                return True
        except ValueError:
            pass
        
        # Allow access to Python standard library and system files
        path_str = str(path).lower()
        allowed_system_paths = [
            'python',
            'windows\\system32',
            'program files\\python',
            'appdata\\local\\temp'
        ]
        
        return any(allowed in path_str for allowed in allowed_system_paths)
    
    def _is_suspicious_connection(self, connection) -> bool:
        """Check if network connection is suspicious."""
        if not connection.raddr:
            return False
        
        remote_ip = connection.raddr.ip
        remote_port = connection.raddr.port
        
        # Check for connections to suspicious ports
        suspicious_ports = [22, 23, 135, 139, 445, 1433, 3389, 5985, 5986]
        if remote_port in suspicious_ports:
            return True
        
        # Check for connections to private IP ranges (potential lateral movement)
        if remote_ip.startswith(('10.', '172.', '192.168.')):
            return True
        
        return False
    
    def _record_violation(self, violation_type: str, description: str, 
                         severity: str, process_info: Dict[str, Any]) -> None:
        """Record a sandbox violation."""
        violation = SandboxViolation(
            timestamp=datetime.now(),
            violation_type=violation_type,
            description=description,
            severity=severity,
            process_info=process_info
        )
        
        self._violations.append(violation)
        self.logger.warning(f"Sandbox violation detected: {description}")
        
        if self.violation_callback:
            self.violation_callback(violation)
    
    def get_violations(self) -> List[SandboxViolation]:
        """Get all recorded violations."""
        return self._violations.copy()
    
    def get_critical_violations(self) -> List[SandboxViolation]:
        """Get only critical violations."""
        return [v for v in self._violations if v.severity == "critical"]
    
    def has_critical_violations(self) -> bool:
        """Check if any critical violations have been detected."""
        return any(v.severity == "critical" for v in self._violations)