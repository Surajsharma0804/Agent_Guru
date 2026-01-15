"""
Built-in Skills for GURU

Provides essential skills that come pre-installed with GURU:
- SystemInfo: System information and health monitoring
- FileOps: Safe file operations with permission validation
- AppControl: Application launching and management
- VectorTextTransformer: Text processing and manipulation utilities
"""

from pathlib import Path
from typing import Dict

from .manifest import PermissionSet, PermissionType, ResourceLimits, RiskLevel, RollbackStrategy, SkillManifest


def create_system_info_skill() -> SkillManifest:
    """Create SystemInfo skill manifest."""
    return SkillManifest(
        skill_id="system-info",
        name="System Information",
        description="Provides system information, health monitoring, and diagnostics",
        version="1.0.0",
        author="GURU Built-in",
        permissions=PermissionSet(
            permissions={PermissionType.SYSTEM_INFO}, filesystem_paths=[], network_hosts=[], ui_applications=[]
        ),
        risk_level=RiskLevel.LOW,
        resource_limits=ResourceLimits(
            max_cpu_percent=10.0,
            max_memory_mb=64,
            max_disk_mb=1,
            max_network_kb=0,
            max_execution_time_seconds=10,
            max_file_handles=10,
            max_processes=1,
        ),
        entry_point="system_info.py",
        supported_platforms=["windows"],
        dependencies=[],
        side_effects=["reads_system_information"],
        rollback_strategy=RollbackStrategy("none"),
        max_calls_per_minute=30,
        max_calls_per_hour=1000,
        max_concurrent_executions=3,
        metadata={"category": "system", "required_parameters": [], "optional_parameters": ["info_type"]},
    )


def create_file_ops_skill() -> SkillManifest:
    """Create FileOps skill manifest."""
    return SkillManifest(
        skill_id="file-ops",
        name="File Operations",
        description="Safe file operations with permission validation",
        version="1.0.0",
        author="GURU Built-in",
        permissions=PermissionSet(
            permissions={PermissionType.FILESYSTEM_READ, PermissionType.FILESYSTEM_WRITE},
            filesystem_paths=[
                str(Path.home() / "Documents"),
                str(Path.home() / "Desktop"),
                str(Path.home() / "Downloads"),
            ],
            network_hosts=[],
            ui_applications=[],
        ),
        risk_level=RiskLevel.MEDIUM,
        resource_limits=ResourceLimits(
            max_cpu_percent=20.0,
            max_memory_mb=128,
            max_disk_mb=50,
            max_network_kb=0,
            max_execution_time_seconds=30,
            max_file_handles=20,
            max_processes=1,
        ),
        entry_point="file_ops.py",
        supported_platforms=["windows"],
        dependencies=[],
        side_effects=["modifies_files", "creates_files", "deletes_files"],
        rollback_strategy=RollbackStrategy(
            strategy_type="file_restore", rollback_data={"backup_location": "temp/backups"}, cleanup_commands=[]
        ),
        max_calls_per_minute=20,
        max_calls_per_hour=500,
        max_concurrent_executions=2,
        metadata={
            "category": "file_system",
            "required_parameters": ["operation"],
            "optional_parameters": ["path", "content", "destination"],
        },
    )


def create_app_control_skill() -> SkillManifest:
    """Create AppControl skill manifest."""
    return SkillManifest(
        skill_id="app-control",
        name="Application Control",
        description="Launch and manage applications with permission validation",
        version="1.0.0",
        author="GURU Built-in",
        permissions=PermissionSet(
            permissions={PermissionType.PROCESS_CONTROL, PermissionType.UI_AUTOMATION},
            filesystem_paths=[],
            network_hosts=[],
            ui_applications=["notepad.exe", "calc.exe", "mspaint.exe", "explorer.exe"],
        ),
        risk_level=RiskLevel.HIGH,
        resource_limits=ResourceLimits(
            max_cpu_percent=30.0,
            max_memory_mb=256,
            max_disk_mb=10,
            max_network_kb=0,
            max_execution_time_seconds=60,
            max_file_handles=30,
            max_processes=3,
        ),
        entry_point="app_control.py",
        supported_platforms=["windows"],
        dependencies=[],
        side_effects=["launches_applications", "modifies_processes"],
        rollback_strategy=RollbackStrategy(
            strategy_type="process_kill", rollback_data={"track_launched_processes": True}, cleanup_commands=[]
        ),
        max_calls_per_minute=10,
        max_calls_per_hour=200,
        max_concurrent_executions=1,
        metadata={
            "category": "application",
            "required_parameters": ["operation"],
            "optional_parameters": ["application", "arguments", "working_directory"],
        },
    )


def create_vector_text_transformer_skill() -> SkillManifest:
    """Create VectorTextTransformer skill manifest."""
    return SkillManifest(
        skill_id="text-processor",
        name="Text Processor",
        description="Text processing and manipulation utilities",
        version="1.0.0",
        author="GURU Built-in",
        permissions=PermissionSet(
            permissions=set(),  # No special permissions needed
            filesystem_paths=[],
            network_hosts=[],
            ui_applications=[],
        ),
        risk_level=RiskLevel.LOW,
        resource_limits=ResourceLimits(
            max_cpu_percent=15.0,
            max_memory_mb=128,
            max_disk_mb=5,
            max_network_kb=0,
            max_execution_time_seconds=15,
            max_file_handles=5,
            max_processes=1,
        ),
        entry_point="text_processor.py",
        supported_platforms=["windows"],
        dependencies=[],
        side_effects=["processes_text"],
        rollback_strategy=RollbackStrategy("none"),
        max_calls_per_minute=50,
        max_calls_per_hour=2000,
        max_concurrent_executions=5,
        metadata={"category": "text", "required_parameters": ["operation", "text"], "optional_parameters": ["options"]},
    )


# Skill implementation code templates
SYSTEM_INFO_SKILL_CODE = '''
"""
System Information Skill Implementation
"""

import psutil
import platform
import json
from datetime import datetime

def get_system_info(info_type="basic"):
    """Get system information based on requested type."""

    if info_type == "basic":
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "hostname": platform.node(),
            "python_version": platform.python_version(),
            "timestamp": datetime.now().isoformat()
        }

    elif info_type == "performance":
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "percent_used": psutil.virtual_memory().percent
            },
            "disk": {
                "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                "free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
                "percent_used": psutil.disk_usage('/').percent
            },
            "timestamp": datetime.now().isoformat()
        }

    elif info_type == "processes":
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by CPU usage and return top 10
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        return {
            "top_processes": processes[:10],
            "total_processes": len(processes),
            "timestamp": datetime.now().isoformat()
        }

    else:
        raise ValueError(f"Unknown info_type: {info_type}")

# Main execution
try:
    info_type = parameters.get("info_type", "basic")
    result = get_system_info(info_type)
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
'''

FILE_OPS_SKILL_CODE = '''
"""
File Operations Skill Implementation
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime

def perform_file_operation(operation, path=None, content=None, destination=None):
    """Perform file operation with safety checks."""

    if operation == "read":
        if not path:
            raise ValueError("path parameter required for read operation")

        if not validate_file_access(path):
            raise PermissionError(f"Access denied to path: {path}")

        with safe_open(path, 'r', encoding='utf-8') as f:
            return {
                "operation": "read",
                "path": path,
                "content": f.read(),
                "size_bytes": os.path.getsize(path),
                "timestamp": datetime.now().isoformat()
            }

    elif operation == "write":
        if not path or content is None:
            raise ValueError("path and content parameters required for write operation")

        if not validate_file_access(path):
            raise PermissionError(f"Access denied to path: {path}")

        # Create backup if file exists
        path_obj = Path(path)
        backup_path = None
        if path_obj.exists():
            backup_path = path_obj.with_suffix(path_obj.suffix + '.backup')
            shutil.copy2(path, backup_path)

        with safe_open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        return {
            "operation": "write",
            "path": path,
            "bytes_written": len(content.encode('utf-8')),
            "backup_created": str(backup_path) if backup_path else None,
            "timestamp": datetime.now().isoformat()
        }

    elif operation == "copy":
        if not path or not destination:
            raise ValueError("path and destination parameters required for copy operation")

        if not validate_file_access(path) or not validate_file_access(destination):
            raise PermissionError("Access denied to source or destination path")

        shutil.copy2(path, destination)

        return {
            "operation": "copy",
            "source": path,
            "destination": destination,
            "size_bytes": os.path.getsize(destination),
            "timestamp": datetime.now().isoformat()
        }

    elif operation == "list":
        if not path:
            path = "."

        if not validate_file_access(path):
            raise PermissionError(f"Access denied to path: {path}")

        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if path_obj.is_file():
            return {
                "operation": "list",
                "path": path,
                "type": "file",
                "size_bytes": path_obj.stat().st_size,
                "timestamp": datetime.now().isoformat()
            }

        items = []
        for item in path_obj.iterdir():
            try:
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size_bytes": stat.st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except (OSError, PermissionError):
                pass

        return {
            "operation": "list",
            "path": path,
            "items": items,
            "count": len(items),
            "timestamp": datetime.now().isoformat()
        }

    else:
        raise ValueError(f"Unknown operation: {operation}")

# Main execution
try:
    operation = parameters.get("operation")
    if not operation:
        raise ValueError("operation parameter is required")

    result = perform_file_operation(
        operation=operation,
        path=parameters.get("path"),
        content=parameters.get("content"),
        destination=parameters.get("destination")
    )

    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
'''

APP_CONTROL_SKILL_CODE = '''
"""
Application Control Skill Implementation
"""

import subprocess
import psutil
import json
import time
from datetime import datetime
from pathlib import Path

def perform_app_operation(operation, application=None, arguments=None, working_directory=None):
    """Perform application control operation."""

    if operation == "launch":
        if not application:
            raise ValueError("application parameter required for launch operation")

        # Validate application is in allowed list
        allowed_apps = [
            "notepad.exe", "calc.exe", "mspaint.exe", "explorer.exe"
        ]

        app_name = Path(application).name.lower()
        if app_name not in [app.lower() for app in allowed_apps]:
            raise PermissionError(f"Application not in allowed list: {application}")

        # Prepare command
        cmd = [application]
        if arguments:
            if isinstance(arguments, str):
                cmd.extend(arguments.split())
            elif isinstance(arguments, list):
                cmd.extend(arguments)

        # Launch process
        try:
            process = subprocess.Popen(
                cmd,
                cwd=working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait a moment to see if process starts successfully
            time.sleep(1)

            if process.poll() is None:
                # Process is still running
                return {
                    "operation": "launch",
                    "application": application,
                    "pid": process.pid,
                    "status": "running",
                    "command": cmd,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Process exited quickly
                stdout, stderr = process.communicate()
                return {
                    "operation": "launch",
                    "application": application,
                    "status": "exited",
                    "exit_code": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            raise RuntimeError(f"Failed to launch application: {e}")

    elif operation == "list":
        # List running processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
            try:
                info = proc.info
                if info['exe']:  # Only include processes with executable paths
                    info['create_time'] = datetime.fromtimestamp(info['create_time']).isoformat()
                    processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by creation time (newest first)
        processes.sort(key=lambda x: x['create_time'], reverse=True)

        return {
            "operation": "list",
            "processes": processes[:20],  # Return top 20
            "total_count": len(processes),
            "timestamp": datetime.now().isoformat()
        }

    elif operation == "status":
        if not application:
            raise ValueError("application parameter required for status operation")

        # Find processes matching application name
        matching_processes = []
        app_name = Path(application).name.lower()

        for proc in psutil.process_iter(['pid', 'name', 'exe', 'status', 'cpu_percent', 'memory_percent']):
            try:
                if proc.info['name'].lower() == app_name:
                    matching_processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "operation": "status",
            "application": application,
            "running_instances": len(matching_processes),
            "processes": matching_processes,
            "timestamp": datetime.now().isoformat()
        }

    else:
        raise ValueError(f"Unknown operation: {operation}")

# Main execution
try:
    operation = parameters.get("operation")
    if not operation:
        raise ValueError("operation parameter is required")

    result = perform_app_operation(
        operation=operation,
        application=parameters.get("application"),
        arguments=parameters.get("arguments"),
        working_directory=parameters.get("working_directory")
    )

    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
'''

TEXT_PROCESSOR_SKILL_CODE = '''
"""
Text Processor Skill Implementation
"""

import re
import json
from datetime import datetime
from typing import Dict, Any, List

def perform_text_operation(operation: str, text: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Perform text processing operation."""

    if options is None:
        options = {}

    if operation == "count":
        return {
            "operation": "count",
            "characters": len(text),
            "characters_no_spaces": len(text.replace(" ", "")),
            "words": len(text.split()),
            "lines": len(text.splitlines()),
            "paragraphs": len([p for p in text.split("\\n\\n") if p.strip()]),
            "timestamp": datetime.now().isoformat()
        }

    elif operation == "transform":
        transform_type = options.get("type", "upper")

        if transform_type == "upper":
            result_text = text.upper()
        elif transform_type == "lower":
            result_text = text.lower()
        elif transform_type == "title":
            result_text = text.title()
        elif transform_type == "capitalize":
            result_text = text.capitalize()
        elif transform_type == "reverse":
            result_text = text[::-1]
        elif transform_type == "strip":
            result_text = text.strip()
        else:
            raise ValueError(f"Unknown transform type: {transform_type}")

        return {
            "operation": "transform",
            "type": transform_type,
            "original_length": len(text),
            "result_length": len(result_text),
            "result": result_text,
            "timestamp": datetime.now().isoformat()
        }

    elif operation == "search":
        pattern = options.get("pattern", "")
        if not pattern:
            raise ValueError("pattern option required for search operation")

        case_sensitive = options.get("case_sensitive", False)
        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            matches = re.finditer(pattern, text, flags)
            match_list = []

            for match in matches:
                match_list.append({
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "groups": match.groups()
                })

            return {
                "operation": "search",
                "pattern": pattern,
                "case_sensitive": case_sensitive,
                "matches_found": len(match_list),
                "matches": match_list,
                "timestamp": datetime.now().isoformat()
            }

        except re.error as _e:
            raise ValueError(f"Invalid regex pattern: {e}")

    elif operation == "replace":
        pattern = options.get("pattern", "")
        replacement = options.get("replacement", "")

        if not pattern:
            raise ValueError("pattern option required for replace operation")

        case_sensitive = options.get("case_sensitive", False)
        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            result_text, count = re.subn(pattern, replacement, text, flags=flags)

            return {
                "operation": "replace",
                "pattern": pattern,
                "replacement": replacement,
                "case_sensitive": case_sensitive,
                "replacements_made": count,
                "original_length": len(text),
                "result_length": len(result_text),
                "result": result_text,
                "timestamp": datetime.now().isoformat()
            }

        except re.error as _e:
            raise ValueError(f"Invalid regex pattern: {e}")

    elif operation == "extract":
        extract_type = options.get("type", "lines")

        if extract_type == "lines":
            start_line = options.get("start_line", 1)
            end_line = options.get("end_line", None)

            lines = text.splitlines()
            if end_line is None:
                end_line = len(lines)

            # Convert to 0-based indexing
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            extracted_lines = lines[start_idx:end_idx]

            return {
                "operation": "extract",
                "type": "lines",
                "start_line": start_line,
                "end_line": end_line,
                "lines_extracted": len(extracted_lines),
                "result": "\\n".join(extracted_lines),
                "timestamp": datetime.now().isoformat()
            }

        elif extract_type == "words":
            start_word = options.get("start_word", 1)
            end_word = options.get("end_word", None)

            words = text.split()
            if end_word is None:
                end_word = len(words)

            # Convert to 0-based indexing
            start_idx = max(0, start_word - 1)
            end_idx = min(len(words), end_word)

            extracted_words = words[start_idx:end_idx]

            return {
                "operation": "extract",
                "type": "words",
                "start_word": start_word,
                "end_word": end_word,
                "words_extracted": len(extracted_words),
                "result": " ".join(extracted_words),
                "timestamp": datetime.now().isoformat()
            }

        else:
            raise ValueError(f"Unknown extract type: {extract_type}")

    else:
        raise ValueError(f"Unknown operation: {operation}")

# Main execution
try:
    operation = parameters.get("operation")
    text = parameters.get("text")
    options = parameters.get("options", {})

    if not operation:
        raise ValueError("operation parameter is required")

    if text is None:
        raise ValueError("text parameter is required")

    result = perform_text_operation(operation, text, options)
    print(json.dumps(result, indent=2))

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
'''

# Skill code mapping
BUILTIN_SKILL_CODES = {
    "system-info": SYSTEM_INFO_SKILL_CODE,
    "file-ops": FILE_OPS_SKILL_CODE,
    "app-control": APP_CONTROL_SKILL_CODE,
    "text-processor": TEXT_PROCESSOR_SKILL_CODE,
}

# Skill manifest creators
BUILTIN_SKILL_MANIFESTS = {
    "system-info": create_system_info_skill,
    "file-ops": create_file_ops_skill,
    "app-control": create_app_control_skill,
    "text-processor": create_vector_text_transformer_skill,
}


def get_builtin_skills() -> Dict[str, SkillManifest]:
    """Get all built-in skill manifests."""
    return {skill_id: creator() for skill_id, creator in BUILTIN_SKILL_MANIFESTS.items()}


def get_builtin_skill_code(skill_id: str) -> str:
    """Get the code for a built-in skill."""
    if skill_id not in BUILTIN_SKILL_CODES:
        raise ValueError(f"Unknown built-in skill: {skill_id}")

    return BUILTIN_SKILL_CODES[skill_id]
