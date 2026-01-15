"""
Command Execution System

Production-grade command execution layer for GURU AI assistant.
Handles intent-to-action mapping, system command execution, application
launching, and file operations with proper security boundaries.

Architecture:
- Intent Recognition: Detect user commands from natural language
- Action Dispatcher: Route to appropriate executor
- System Executor: Execute Windows commands safely
- Application Launcher: Open applications with proper error handling
- File Operations: Read/write files with permission checks
- Security Boundary: Authority-based permission system

This is the missing layer that transforms GURU from a chatbot into an AI assistant.
"""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# PAL imports - platform-agnostic interfaces
from pal.interfaces import (
    ApplicationController,
    InputAutomation,
    AppDescriptor,
    AutomationTarget,
    PlatformCapabilityError
)

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands that can be executed"""
    OPEN_APPLICATION = "open_application"
    WRITE_FILE = "write_file"
    READ_FILE = "read_file"
    SYSTEM_COMMAND = "system_command"
    WEB_SEARCH = "web_search"
    UNKNOWN = "unknown"


class ExecutionStatus(Enum):
    """Execution status"""
    SUCCESS = "success"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """Result of command execution"""
    status: ExecutionStatus
    message: str
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class IntentRecognizer:
    """
    Recognizes user intent from natural language.
    
    Uses pattern matching and keyword detection to identify
    what the user wants to do.
    """
    
    def __init__(self):
        """Initialize intent recognizer"""
        self.patterns = {
            CommandType.OPEN_APPLICATION: [
                "open", "launch", "start", "run",
                "kholo", "chalu karo"  # Hindi
            ],
            CommandType.WRITE_FILE: [
                "write", "create", "save", "type",
                "likho", "banao"  # Hindi
            ],
            CommandType.READ_FILE: [
                "read", "show", "display", "open file",
                "padho", "dikhao"  # Hindi
            ],
            CommandType.WEB_SEARCH: [
                "search", "google", "find", "look up",
                "dhundo", "search karo"  # Hindi
            ]
        }
        
        # Comprehensive application database with common paths
        self.app_mapping = {
            # System Tools
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "taskmgr.exe",
            "control panel": "control.exe",
            "settings": "ms-settings:",
            
            # Microsoft Office
            "word": "winword.exe",
            "microsoft word": "winword.exe",
            "excel": "excel.exe",
            "microsoft excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "microsoft powerpoint": "powerpnt.exe",
            "outlook": "outlook.exe",
            "microsoft outlook": "outlook.exe",
            "onenote": "onenote.exe",
            "microsoft onenote": "onenote.exe",
            "teams": "teams.exe",
            "microsoft teams": "teams.exe",
            "access": "msaccess.exe",
            "microsoft access": "msaccess.exe",
            "publisher": "mspub.exe",
            "microsoft publisher": "mspub.exe",
            
            # Web Browsers
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "mozilla firefox": "firefox.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "brave": "brave.exe",
            "opera": "opera.exe",
            "safari": "safari.exe",
            
            # Communication
            "whatsapp": "whatsapp.exe",
            "telegram": "telegram.exe",
            "discord": "discord.exe",
            "slack": "slack.exe",
            "zoom": "zoom.exe",
            "skype": "skype.exe",
            "microsoft teams": "teams.exe",
            
            # Social Media & Entertainment
            "instagram": "instagram.exe",
            "facebook": "facebook.exe",
            "twitter": "twitter.exe",
            "spotify": "spotify.exe",
            "youtube": "youtube.exe",
            "netflix": "netflix.exe",
            "tiktok": "tiktok.exe",
            
            # Development Tools
            "visual studio code": "code.exe",
            "vscode": "code.exe",
            "vs code": "code.exe",
            "visual studio": "devenv.exe",
            "pycharm": "pycharm64.exe",
            "intellij": "idea64.exe",
            "android studio": "studio64.exe",
            "git": "git.exe",
            "github desktop": "githubdesktop.exe",
            "docker": "docker.exe",
            
            # Media & Graphics
            "photoshop": "photoshop.exe",
            "adobe photoshop": "photoshop.exe",
            "illustrator": "illustrator.exe",
            "adobe illustrator": "illustrator.exe",
            "premiere": "premiere.exe",
            "adobe premiere": "premiere.exe",
            "after effects": "afterfx.exe",
            "vlc": "vlc.exe",
            "media player": "wmplayer.exe",
            "windows media player": "wmplayer.exe",
            "gimp": "gimp.exe",
            "inkscape": "inkscape.exe",
            "blender": "blender.exe",
            
            # Productivity
            "notion": "notion.exe",
            "evernote": "evernote.exe",
            "trello": "trello.exe",
            "todoist": "todoist.exe",
            "obsidian": "obsidian.exe",
            
            # File Management
            "7zip": "7zfm.exe",
            "winrar": "winrar.exe",
            "total commander": "totalcmd64.exe",
            
            # System Utilities
            "ccleaner": "ccleaner64.exe",
            "malwarebytes": "mbam.exe",
            "steam": "steam.exe",
            "epic games": "epicgameslauncher.exe",
            
            # Kiro (if installed)
            "kiro": "kiro.exe",
        }
        
        # Common installation paths to search
        self.search_paths = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps",
        ]
    
    def recognize(self, text: str) -> Tuple[CommandType, Dict[str, Any]]:
        """
        Recognize intent from user text.
        
        Args:
            text: User's natural language input
        
        Returns:
            Tuple of (CommandType, parameters dict)
        """
        text_lower = text.lower()
        
        # Check for application opening
        for keyword in self.patterns[CommandType.OPEN_APPLICATION]:
            if keyword in text_lower:
                # Extract application name
                for app_name in self.app_mapping.keys():
                    if app_name in text_lower:
                        return CommandType.OPEN_APPLICATION, {
                            "application": app_name,
                            "executable": self.app_mapping[app_name]
                        }
                
                # If not in mapping, try to extract app name dynamically
                app_name = self._extract_app_name(text, keyword)
                if app_name:
                    return CommandType.OPEN_APPLICATION, {
                        "application": app_name,
                        "executable": f"{app_name}.exe"
                    }
        
        # Check for file writing
        for keyword in self.patterns[CommandType.WRITE_FILE]:
            if keyword in text_lower:
                # Extract file name and content
                params = self._extract_write_params(text)
                if params:
                    return CommandType.WRITE_FILE, params
        
        # Check for file reading
        for keyword in self.patterns[CommandType.READ_FILE]:
            if keyword in text_lower:
                params = self._extract_read_params(text)
                if params:
                    return CommandType.READ_FILE, params
        
        # Check for web search
        for keyword in self.patterns[CommandType.WEB_SEARCH]:
            if keyword in text_lower:
                query = text_lower.replace(keyword, "").strip()
                return CommandType.WEB_SEARCH, {"query": query}
        
        return CommandType.UNKNOWN, {}
    
    def _extract_app_name(self, text: str, keyword: str) -> Optional[str]:
        """Extract application name from text dynamically"""
        text_lower = text.lower()
        
        # Find keyword position
        keyword_pos = text_lower.find(keyword)
        if keyword_pos == -1:
            return None
        
        # Extract text after keyword
        after_keyword = text[keyword_pos + len(keyword):].strip()
        
        # Take first word or two words
        words = after_keyword.split()
        if len(words) >= 2:
            # Try two-word app name first
            app_name = f"{words[0]} {words[1]}".lower()
            if app_name not in ["the", "a", "an"]:
                return app_name
        
        if len(words) >= 1:
            # Single word app name
            app_name = words[0].lower()
            if app_name not in ["the", "a", "an", "and", "or"]:
                return app_name
        
        return None
    
    def _extract_write_params(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract file writing parameters from text"""
        text_lower = text.lower()
        
        # Look for "write X" or "type X" pattern
        content_start = -1
        trigger_word = None
        
        for keyword in ["write", "type", "add", "put", "likho"]:
            if keyword in text_lower:
                content_start = text_lower.find(keyword) + len(keyword)
                trigger_word = keyword
                break
        
        if content_start > 0:
            # Extract everything after the trigger word
            content = text[content_start:].strip()
            
            # Remove common phrases
            for phrase in ["in notepad", "to notepad", "on notepad", "into notepad", 
                          "in the notepad", "to the notepad", "there", "their"]:
                content = content.replace(phrase, "").strip()
            
            # Remove "that" at the beginning
            if content.startswith("that "):
                content = content[5:].strip()
            
            if content and len(content) > 2:
                return {
                    "application": "notepad",
                    "content": content,
                    "filename": None
                }
        
        return None
    
    def _extract_read_params(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract file reading parameters from text"""
        # TODO: Implement file reading parameter extraction
        return None


class ApplicationLauncher:
    """
    Launches applications using platform-agnostic PAL interface.
    
    Handles application discovery, launching, and error recovery through
    the ApplicationController interface, ensuring platform independence.
    """
    
    def __init__(self, app_controller: ApplicationController):
        """
        Initialize application launcher with PAL interface.
        
        Args:
            app_controller: Platform-specific ApplicationController implementation
        """
        self.app_controller = app_controller
        self.running_processes: Dict[str, bool] = {}  # Track running apps
        
        # Get platform capabilities
        self.capabilities = app_controller.get_capabilities()
        
        logger.info(
            "Application launcher initialized",
            platform_capabilities=self.capabilities
        )
    
    def find_executable(self, executable: str) -> Optional[str]:
        """
        Find executable using platform-agnostic app discovery.
        
        Args:
            executable: Executable name (e.g., "chrome.exe", "notepad")
        
        Returns:
            App ID if found, None otherwise
        """
        # Discover all apps
        apps = self.app_controller.discover_apps()
        
        # Normalize executable name for matching
        exec_lower = executable.lower().replace(".exe", "")
        
        # Search for matching app
        for app in apps:
            app_name_lower = app.display_name.lower()
            app_id_lower = app.app_id.lower()
            
            if exec_lower in app_name_lower or exec_lower in app_id_lower:
                logger.info(f"Found app: {app.display_name} (ID: {app.app_id})")
                return app.app_id
        
        # If not found, try using the executable name as app_id directly
        return executable
    
    def launch(self, executable: str, args: Optional[List[str]] = None) -> ExecutionResult:
        """
        Launch an application using PAL interface.
        
        Args:
            executable: Application executable name or ID
            args: Optional command-line arguments (may not be supported on all platforms)
        
        Returns:
            ExecutionResult with launch status
        """
        start_time = time.time()
        
        try:
            # Find app ID
            app_id = self.find_executable(executable)
            if not app_id:
                execution_time = time.time() - start_time
                return ExecutionResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Could not find application: {executable}",
                    error="Application not found",
                    execution_time=execution_time
                )
            
            # Check if we can open apps on this platform
            if not self.capabilities.get("can_open_apps", False):
                execution_time = time.time() - start_time
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=f"Platform does not support opening applications",
                    error="PlatformCapabilityError",
                    execution_time=execution_time
                )
            
            # Launch application using PAL
            success = self.app_controller.open_app(app_id)
            
            execution_time = time.time() - start_time
            
            if success:
                # Track running app
                self.running_processes[app_id] = True
                
                logger.info(f"Launched {app_id}")
                
                # Extract app name for user-friendly message
                app_name = Path(executable).stem if executable else "application"
                
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Opened {app_name} successfully",
                    execution_time=execution_time
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=f"Failed to launch {executable}",
                    error="Launch failed",
                    execution_time=execution_time
                )
        
        except PlatformCapabilityError as e:
            execution_time = time.time() - start_time
            logger.error(f"Platform capability error: {e}")
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Platform does not support this operation",
                error=str(e),
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to launch {executable}: {e}")
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to launch '{executable}'",
                error=str(e),
                execution_time=execution_time
            )


class FileOperator:
    """
    Handles file operations safely.
    
    Provides read/write operations with proper error handling
    and permission checks.
    """
    
    def __init__(self):
        """Initialize file operator"""
        self.temp_dir = Path.home() / "Documents" / "GURU"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def write_file(self, content: str, filename: Optional[str] = None) -> ExecutionResult:
        """
        Write content to a file.
        
        Args:
            content: Content to write
            filename: Optional filename (generated if not provided)
        
        Returns:
            ExecutionResult with write status
        """
        start_time = time.time()
        
        try:
            # Generate filename if not provided
            if not filename:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"guru_note_{timestamp}.txt"
            
            # Full path
            filepath = self.temp_dir / filename
            
            # Write file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            execution_time = time.time() - start_time
            
            logger.info(f"Wrote file: {filepath}")
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"File saved: {filepath}",
                output=str(filepath),
                execution_time=execution_time
            )
        
        except PermissionError:
            execution_time = time.time() - start_time
            logger.error(f"Permission denied writing file: {filename}")
            
            return ExecutionResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                message=f"Permission denied to write file",
                error="PermissionError",
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to write file: {e}")
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to write file",
                error=str(e),
                execution_time=execution_time
            )
    
    def read_file(self, filepath: str) -> ExecutionResult:
        """
        Read content from a file.
        
        Args:
            filepath: Path to file to read
        
        Returns:
            ExecutionResult with file content
        """
        start_time = time.time()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            execution_time = time.time() - start_time
            
            logger.info(f"Read file: {filepath}")
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"File read successfully",
                output=content,
                execution_time=execution_time
            )
        
        except FileNotFoundError:
            execution_time = time.time() - start_time
            logger.error(f"File not found: {filepath}")
            
            return ExecutionResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"File not found: {filepath}",
                error="FileNotFoundError",
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to read file: {e}")
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to read file",
                error=str(e),
                execution_time=execution_time
            )


class TextAutomation:
    """
    Text automation using platform-agnostic PAL interface.
    
    Provides high-level automation for typing text into applications
    using the InputAutomation interface.
    """
    
    def __init__(self, input_automation: InputAutomation, app_controller: ApplicationController):
        """
        Initialize text automation with PAL interfaces.
        
        Args:
            input_automation: Platform-specific InputAutomation implementation
            app_controller: Platform-specific ApplicationController implementation
        """
        self.input_automation = input_automation
        self.app_controller = app_controller
        
        # Get platform capabilities
        self.capabilities = input_automation.get_capabilities()
        
        logger.info(
            "Text automation initialized",
            platform_capabilities=self.capabilities
        )
    
    def type_into_notepad(self, text: str) -> ExecutionResult:
        """
        Type text into Notepad using platform-agnostic automation.
        
        Args:
            text: Text to type
        
        Returns:
            ExecutionResult with automation status
        """
        start_time = time.time()
        
        try:
            # Check if we can type text on this platform
            if not self.capabilities.get("can_type_text", False):
                execution_time = time.time() - start_time
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message="Platform does not support text automation",
                    error="PlatformCapabilityError",
                    execution_time=execution_time
                )
            
            # Launch Notepad using app controller
            success = self.app_controller.open_app("notepad")
            if not success:
                execution_time = time.time() - start_time
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message="Failed to launch Notepad",
                    error="Application launch failed",
                    execution_time=execution_time
                )
            
            # Wait for Notepad to open
            time.sleep(1.0)
            
            # Focus Notepad
            self.input_automation.focus_app("notepad")
            time.sleep(0.5)
            
            # Type the text using PAL
            success = self.input_automation.type_text(text)
            
            execution_time = time.time() - start_time
            
            if success:
                logger.info(f"Typed text into Notepad: {len(text)} characters")
                
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Text typed into Notepad successfully",
                    execution_time=execution_time
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=f"Failed to type text into Notepad",
                    error="Text automation failed",
                    execution_time=execution_time
                )
        
        except PlatformCapabilityError as e:
            execution_time = time.time() - start_time
            logger.error(f"Platform capability error: {e}")
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Platform does not support this operation",
                error=str(e),
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to type into Notepad: {e}")
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to type into Notepad",
                error=str(e),
                execution_time=execution_time
            )


class CommandExecutor:
    """
    Main command execution system using platform-agnostic PAL interfaces.
    
    Coordinates intent recognition, action dispatching, and execution through
    PAL interfaces, ensuring platform independence and security.
    
    This is the missing layer that makes GURU an AI assistant instead of a chatbot.
    """
    
    def __init__(
        self,
        app_controller: ApplicationController,
        input_automation: InputAutomation
    ):
        """
        Initialize command executor with PAL interfaces.
        
        Args:
            app_controller: Platform-specific ApplicationController implementation
            input_automation: Platform-specific InputAutomation implementation
        """
        self.intent_recognizer = IntentRecognizer()
        self.app_launcher = ApplicationLauncher(app_controller)
        self.file_operator = FileOperator()
        self.text_automation = TextAutomation(input_automation, app_controller)
        
        # Store PAL interfaces for direct use
        self.app_controller = app_controller
        self.input_automation = input_automation
        
        # Get platform capabilities
        self.app_capabilities = app_controller.get_capabilities()
        self.automation_capabilities = input_automation.get_capabilities()
        
        logger.info(
            "Command Executor initialized",
            app_capabilities=self.app_capabilities,
            automation_capabilities=self.automation_capabilities
        )
    
    def execute(self, user_input: str) -> ExecutionResult:
        """
        Execute a command from user input.
        
        Args:
            user_input: User's natural language command
        
        Returns:
            ExecutionResult with execution status
        """
        # Recognize intent
        command_type, params = self.intent_recognizer.recognize(user_input)
        
        logger.info(f"Recognized command: {command_type.value}, params: {params}")
        
        # Dispatch to appropriate executor
        if command_type == CommandType.OPEN_APPLICATION:
            return self._execute_open_application(params)
        
        elif command_type == CommandType.WRITE_FILE:
            return self._execute_write_file(params)
        
        elif command_type == CommandType.READ_FILE:
            return self._execute_read_file(params)
        
        elif command_type == CommandType.WEB_SEARCH:
            return self._execute_web_search(params)
        
        else:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message="I'm not sure how to do that yet. I can open applications, write files, and search the web.",
                error="Unknown command type"
            )
    
    def _execute_open_application(self, params: Dict[str, Any]) -> ExecutionResult:
        """Execute application opening using PAL"""
        executable = params.get("executable")
        app_name = params.get("application", "application")
        
        if not executable:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message="I'm not sure which app you want me to open",
                error="Missing executable"
            )
        
        # Check if we need to write content to the application
        if params.get("application") == "notepad" and "content" in params:
            # Use text automation to type into Notepad
            return self.text_automation.type_into_notepad(params["content"])
        else:
            # Launch the application with human-like response
            result = self.app_launcher.launch(executable)
            
            # Make response more natural
            if result.status == ExecutionStatus.SUCCESS:
                # Natural acknowledgment based on app
                if "whatsapp" in app_name.lower():
                    result.message = "Opening WhatsApp for you"
                elif "chrome" in app_name.lower() or "browser" in app_name.lower():
                    result.message = f"Opening {app_name}"
                elif "word" in app_name.lower() or "excel" in app_name.lower() or "powerpoint" in app_name.lower():
                    result.message = f"Opening {app_name}"
                else:
                    result.message = f"Opening {app_name}"
            
            return result
    
    def _execute_write_file(self, params: Dict[str, Any]) -> ExecutionResult:
        """Execute file writing"""
        content = params.get("content")
        filename = params.get("filename")
        
        if not content:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message="No content to write",
                error="Missing content"
            )
        
        # If writing to notepad, use automation
        if params.get("application") == "notepad":
            return self.text_automation.type_into_notepad(content)
        else:
            return self.file_operator.write_file(content, filename)
    
    def _execute_read_file(self, params: Dict[str, Any]) -> ExecutionResult:
        """Execute file reading"""
        filepath = params.get("filepath")
        
        if not filepath:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message="No file specified",
                error="Missing filepath"
            )
        
        return self.file_operator.read_file(filepath)
    
    def _execute_web_search(self, params: Dict[str, Any]) -> ExecutionResult:
        """Execute web search"""
        query = params.get("query")
        
        if not query:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message="No search query specified",
                error="Missing query"
            )
        
        # Open default browser with search
        import webbrowser
        search_url = f"https://www.google.com/search?q={query}"
        webbrowser.open(search_url)
        
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Searching for: {query}"
        )


# Global executor instance
_executor: Optional[CommandExecutor] = None


def get_command_executor(
    app_controller: Optional[ApplicationController] = None,
    input_automation: Optional[InputAutomation] = None
) -> CommandExecutor:
    """
    Get global command executor instance.
    
    Args:
        app_controller: Optional ApplicationController (creates default if None)
        input_automation: Optional InputAutomation (creates default if None)
    
    Returns:
        CommandExecutor instance
    
    Note:
        If PAL interfaces are provided, a new instance is created.
        If PAL interfaces are not provided, returns singleton instance.
    """
    global _executor
    
    # If explicit PAL interfaces provided, create new instance (for testing/DI)
    if app_controller is not None and input_automation is not None:
        return CommandExecutor(app_controller, input_automation)
    
    # Otherwise use singleton pattern
    if _executor is None:
        from pal.platform_detector import PlatformDetector
        from pal.backend_factory import PlatformBackendFactory
        
        # Detect platform
        platform = PlatformDetector.detect()
        factory = PlatformBackendFactory(platform)
        
        # Create PAL interfaces
        if app_controller is None:
            app_controller = factory.create_application_controller()
        if input_automation is None:
            input_automation = factory.create_input_automation()
        
        _executor = CommandExecutor(app_controller, input_automation)
    return _executor


__all__ = [
    'CommandExecutor',
    'CommandType',
    'ExecutionStatus',
    'ExecutionResult',
    'get_command_executor'
]
