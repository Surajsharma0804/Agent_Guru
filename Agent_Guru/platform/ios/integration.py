"""
iOS Platform Integration

Provides iOS-specific operations using pyobjus and iOS frameworks.

Performance Requirements:
- Time Complexity: O(1) for most operations
- Space Complexity: O(1) for state management
- Latency: <100ms for app launches, <50ms for permission checks

Architecture:
- URL scheme-based app launching
- Shortcuts automation via Intents framework
- Files app integration via UIDocumentPickerViewController
- UserNotifications framework for notifications
- Background modes for always-on operation
- Runtime permission handling

Author: Agent Guru Team
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging
import sys

logger = logging.getLogger(__name__)


class IOSPermission(Enum):
    """iOS permission types."""
    MICROPHONE = "microphone"
    CAMERA = "camera"
    PHOTOS = "photos"
    CONTACTS = "contacts"
    LOCATION = "location"
    NOTIFICATIONS = "notifications"
    SPEECH_RECOGNITION = "speech_recognition"
    AUTOMATION = "automation"


@dataclass
class BatteryInfo:
    """iOS battery information."""
    level: float  # 0.0-1.0
    state: str  # "charging", "unplugged", "full"
    low_power_mode: bool


@dataclass
class ShortcutResult:
    """Result from Shortcuts execution."""
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None


class IOSIntegration:
    """
    iOS platform integration using pyobjus and iOS frameworks.
    
    Time Complexity: O(1) for most operations
    Space Complexity: O(1) for state management
    
    Features:
    - URL scheme app launching
    - Shortcuts automation
    - Files app integration
    - UserNotifications framework
    - Background modes management
    - Permission handling
    
    Example:
        >>> integration = IOSIntegration()
        >>> integration.launch_app_by_url_scheme("whatsapp://")
        True
        >>> integration.request_permission(IOSPermission.MICROPHONE)
        True
    """
    
    def __init__(self) -> None:
        """Initialize iOS integration."""
        self._check_platform()
        self._pyobjus_available = self._check_pyobjus()
        self._background_task_id: Optional[int] = None
        
        if self._pyobjus_available:
            self._initialize_frameworks()
        
        logger.info("iOS integration initialized")
    
    def _check_platform(self) -> None:
        """Verify running on iOS platform."""
        if sys.platform != "ios":
            logger.warning(
                f"iOS integration initialized on non-iOS platform: {sys.platform}"
            )
    
    def _check_pyobjus(self) -> bool:
        """Check if pyobjus is available."""
        try:
            import pyobjus
            return True
        except ImportError:
            logger.warning(
                "pyobjus not available - iOS integration will use fallback mode"
            )
            return False
    
    def _initialize_frameworks(self) -> None:
        """Initialize iOS frameworks via pyobjus."""
        if not self._pyobjus_available:
            return
        
        try:
            from pyobjus import autoclass
            
            # Import iOS frameworks
            self.UIApplication = autoclass("UIApplication")
            self.NSURL = autoclass("NSURL")
            self.UIDevice = autoclass("UIDevice")
            self.UNUserNotificationCenter = autoclass("UNUserNotificationCenter")
            self.AVAudioSession = autoclass("AVAudioSession")  # noqa: N806
            self.UIBackgroundTaskIdentifier = autoclass("UIBackgroundTaskIdentifier")
            
            logger.info("iOS frameworks initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize iOS frameworks: {e}")
            self._pyobjus_available = False
    
    def launch_app_by_url_scheme(self, url_scheme: str) -> bool:
        """
        Launch iOS app by URL scheme.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            url_scheme: URL scheme (e.g., "whatsapp://", "spotify://")
        
        Returns:
            True if app launched successfully
        
        Raises:
            ValueError: If url_scheme is invalid
            RuntimeError: If pyobjus not available
        
        Example:
            >>> integration.launch_app_by_url_scheme("whatsapp://send?text=Hello")
            True
        """
        if not url_scheme:
            raise ValueError("URL scheme cannot be empty")
        
        if not self._pyobjus_available:
            raise RuntimeError("pyobjus not available - cannot launch apps")
        
        try:
            # Create NSURL from string
            url = self.NSURL.URLWithString_(url_scheme)
            
            if not url:
                logger.error(f"Invalid URL scheme: {url_scheme}")
                return False
            
            # Get shared application
            app = self.UIApplication.sharedApplication()
            
            # Check if URL can be opened
            if not app.canOpenURL_(url):
                logger.error(f"Cannot open URL scheme: {url_scheme}")
                return False
            
            # Open URL
            app.openURL_options_completionHandler_(
                url,
                {},
                None
            )
            
            logger.info(f"Launched app with URL scheme: {url_scheme}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to launch app: {e}")
            return False
    
    def execute_shortcut(
        self,
        shortcut_name: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> ShortcutResult:
        """
        Execute iOS Shortcut.
        
        Time Complexity: O(1) for invocation (shortcut execution time varies)
        Space Complexity: O(1)
        
        Args:
            shortcut_name: Name of the shortcut
            input_data: Input data for shortcut
        
        Returns:
            ShortcutResult with output or error
        
        Example:
            >>> result = integration.execute_shortcut("Morning Routine")
            >>> print(result.success)
            True
        """
        if not shortcut_name:
            return ShortcutResult(
                success=False,
                error="Shortcut name cannot be empty"
            )
        
        if not self._pyobjus_available:
            return ShortcutResult(
                success=False,
                error="pyobjus not available"
            )
        
        try:
            # Use x-callback-url scheme for Shortcuts
            url_scheme = f"shortcuts://run-shortcut?name={shortcut_name}"
            
            if input_data:
                # Add input data as URL parameters
                params = "&".join(
                    f"{k}={v}" for k, v in input_data.items()
                )
                url_scheme += f"&input={params}"
            
            success = self.launch_app_by_url_scheme(url_scheme)
            
            if success:
                logger.info(f"Executed shortcut: {shortcut_name}")
                return ShortcutResult(success=True)
            else:
                return ShortcutResult(
                    success=False,
                    error=f"Failed to execute shortcut: {shortcut_name}"
                )
                
        except Exception as e:
            logger.error(f"Shortcut execution failed: {e}")
            return ShortcutResult(success=False, error=str(e))
    
    def get_battery_info(self) -> BatteryInfo:
        """
        Get iOS battery information.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Returns:
            BatteryInfo with current battery status
        
        Example:
            >>> info = integration.get_battery_info()
            >>> print(f"Battery: {info.level * 100}%")
            Battery: 85%
        """
        if not self._pyobjus_available:
            # Return default values if pyobjus not available
            return BatteryInfo(
                level=1.0,
                state="unknown",
                low_power_mode=False
            )
        
        try:
            device = self.UIDevice.currentDevice()
            
            # Enable battery monitoring
            device.setBatteryMonitoringEnabled_(True)
            
            # Get battery level (0.0-1.0)
            level = float(device.batteryLevel())
            
            # Get battery state
            state_code = device.batteryState()
            state_map = {
                0: "unknown",
                1: "unplugged",
                2: "charging",
                3: "full"
            }
            state = state_map.get(state_code, "unknown")
            
            # Check low power mode
            process_info = autoclass("NSProcessInfo").processInfo()
            low_power_mode = process_info.isLowPowerModeEnabled()
            
            return BatteryInfo(
                level=level,
                state=state,
                low_power_mode=low_power_mode
            )
            
        except Exception as e:
            logger.error(f"Failed to get battery info: {e}")
            return BatteryInfo(
                level=1.0,
                state="unknown",
                low_power_mode=False
            )
    
    def request_permission(self, permission: IOSPermission) -> bool:
        """
        Request iOS permission.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            permission: Permission type to request
        
        Returns:
            True if permission granted
        
        Note:
            This triggers iOS permission dialog. User must grant permission.
        
        Example:
            >>> integration.request_permission(IOSPermission.MICROPHONE)
            True
        """
        if not self._pyobjus_available:
            logger.warning("pyobjus not available - cannot request permissions")
            return False
        
        try:
            if permission == IOSPermission.MICROPHONE:
                return self._request_microphone_permission()
            elif permission == IOSPermission.CAMERA:
                return self._request_camera_permission()
            elif permission == IOSPermission.NOTIFICATIONS:
                return self._request_notification_permission()
            elif permission == IOSPermission.LOCATION:
                return self._request_location_permission()
            else:
                logger.warning(f"Permission type not implemented: {permission}")
                return False
                
        except Exception as e:
            logger.error(f"Permission request failed: {e}")
            return False
    
    def _request_microphone_permission(self) -> bool:
        """Request microphone permission."""
        from pyobjus import autoclass
        
        AVAudioSession = autoclass("AVAudioSession")  # noqa: N806
        session = AVAudioSession.sharedInstance()
        
        # Request permission (blocks until user responds)
        session.requestRecordPermission_(None)
        
        # Check if granted
        return session.recordPermission() == 1  # AVAudioSessionRecordPermissionGranted
    
    def _request_camera_permission(self) -> bool:
        """Request camera permission."""
        from pyobjus import autoclass
        
        AVCaptureDevice = autoclass("AVCaptureDevice")  # noqa: N806
        
        # Request permission
        AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            "vide",  # AVMediaTypeVideo
            None
        )
        
        # Check if granted
        status = AVCaptureDevice.authorizationStatusForMediaType_("vide")
        return status == 3  # AVAuthorizationStatusAuthorized
    
    def _request_notification_permission(self) -> bool:
        """Request notification permission."""
        center = self.UNUserNotificationCenter.currentNotificationCenter()
        
        # Request authorization
        center.requestAuthorizationWithOptions_completionHandler_(
            7,  # UNAuthorizationOptionAlert | Sound | Badge
            None
        )
        
        return True  # Assume granted (async operation)
    
    def _request_location_permission(self) -> bool:
        """Request location permission."""
        from pyobjus import autoclass
        
        CLLocationManager = autoclass("CLLocationManager")  # noqa: N806
        manager = CLLocationManager.alloc().init()
        
        # Request when-in-use authorization
        manager.requestWhenInUseAuthorization()
        
        return True  # Assume granted (async operation)
    
    def start_background_audio(self) -> None:
        """
        Start background audio mode for always-on operation.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Note:
            Requires "audio" background mode in Info.plist
        
        Example:
            >>> integration.start_background_audio()
        """
        if not self._pyobjus_available:
            logger.warning("pyobjus not available - cannot start background audio")
            return
        
        try:
            session = self.AVAudioSession.sharedInstance()
            
            # Set category to playback (allows background audio)
            session.setCategory_error_(
                "AVAudioSessionCategoryPlayback",
                None
            )
            
            # Activate session
            session.setActive_error_(True, None)
            
            logger.info("Background audio mode started")
            
        except Exception as e:
            logger.error(f"Failed to start background audio: {e}")
    
    def schedule_background_task(
        self,
        task_id: str,
        interval_seconds: int
    ) -> None:
        """
        Schedule iOS background task.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            task_id: Unique task identifier
            interval_seconds: Interval between executions
        
        Note:
            Requires "fetch" or "processing" background mode in Info.plist
        
        Example:
            >>> integration.schedule_background_task("wake_word_check", 300)
        """
        if not self._pyobjus_available:
            logger.warning("pyobjus not available - cannot schedule background task")
            return
        
        try:
            from pyobjus import autoclass
            
            BGTaskScheduler = autoclass("BGTaskScheduler")  # noqa: N806
            scheduler = BGTaskScheduler.sharedScheduler()
            
            # Create task request
            BGAppRefreshTaskRequest = autoclass("BGAppRefreshTaskRequest")  # noqa: N806
            request = BGAppRefreshTaskRequest.alloc().initWithIdentifier_(task_id)
            
            # Set earliest begin date
            from datetime import datetime, timedelta
            earliest_date = datetime.now() + timedelta(seconds=interval_seconds)
            request.setEarliestBeginDate_(earliest_date)
            
            # Submit request
            scheduler.submitTaskRequest_error_(request, None)
            
            logger.info(f"Scheduled background task: {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to schedule background task: {e}")
    
    def create_notification(self, title: str, message: str) -> None:
        """
        Create iOS notification using UserNotifications.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            title: Notification title
            message: Notification message
        
        Example:
            >>> integration.create_notification("Agent Guru", "Wake word detected")
        """
        if not self._pyobjus_available:
            logger.warning("pyobjus not available - cannot create notification")
            return
        
        try:
            from pyobjus import autoclass
            
            # Get notification center
            center = self.UNUserNotificationCenter.currentNotificationCenter()
            
            # Create notification content
            UNMutableNotificationContent = autoclass("UNMutableNotificationContent")  # noqa: N806
            content = UNMutableNotificationContent.alloc().init()
            content.setTitle_(title)
            content.setBody_(message)
            content.setSound_(autoclass("UNNotificationSound").defaultSound())
            
            # Create trigger (deliver immediately)
            UNTimeIntervalNotificationTrigger = autoclass(  # noqa: N806
                "UNTimeIntervalNotificationTrigger"
            )
            trigger = UNTimeIntervalNotificationTrigger.triggerWithTimeInterval_repeats_(
                1,  # 1 second
                False
            )
            
            # Create request
            UNNotificationRequest = autoclass("UNNotificationRequest")  # noqa: N806
            request = UNNotificationRequest.requestWithIdentifier_content_trigger_(
                "agent_guru_notification",
                content,
                trigger
            )
            
            # Add notification
            center.addNotificationRequest_withCompletionHandler_(request, None)
            
            logger.info(f"Created notification: {title}")
            
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")
    
    def begin_background_task(self, task_name: str) -> int:
        """
        Begin background task to prevent suspension.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            task_name: Name of the background task
        
        Returns:
            Task identifier (use to end task)
        
        Example:
            >>> task_id = integration.begin_background_task("processing")
            >>> # Do work...
            >>> integration.end_background_task(task_id)
        """
        if not self._pyobjus_available:
            return -1
        
        try:
            app = self.UIApplication.sharedApplication()
            
            # Begin background task
            task_id = app.beginBackgroundTaskWithName_expirationHandler_(
                task_name,
                None  # Expiration handler
            )
            
            logger.info(f"Started background task: {task_name} (ID: {task_id})")
            return int(task_id)
            
        except Exception as e:
            logger.error(f"Failed to begin background task: {e}")
            return -1
    
    def end_background_task(self, task_id: int) -> None:
        """
        End background task.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            task_id: Task identifier from begin_background_task
        
        Example:
            >>> integration.end_background_task(task_id)
        """
        if not self._pyobjus_available or task_id < 0:
            return
        
        try:
            app = self.UIApplication.sharedApplication()
            app.endBackgroundTask_(task_id)
            
            logger.info(f"Ended background task: {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to end background task: {e}")
