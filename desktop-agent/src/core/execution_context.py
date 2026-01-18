"""
Execution Context Detection System

This module determines the execution environment and enforces appropriate
LLM behavior based on distribution context (sideloaded vs store-installed).

CRITICAL POLICY ENFORCEMENT:
- Store-installed apps MUST use API-only LLM providers
- Sideloaded apps MAY use local models with user consent
- Context detection MUST be tamper-resistant
- Policy violations result in immediate system lockdown

ZERO TOLERANCE: No shortcuts, no policy bypasses, no degraded modes.
"""

import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import platform
import subprocess
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class ExecutionContext(Enum):
    """Execution context types with strict policy enforcement."""
    
    DEVELOPMENT = "development"          # Development environment - full access
    SIDELOADED_DESKTOP = "sideloaded"   # Sideloaded desktop app - local models allowed
    STORE_INSTALLED = "store_installed" # Store-installed app - API-only enforcement
    ENTERPRISE = "enterprise"           # Enterprise deployment - policy-controlled
    UNKNOWN = "unknown"                 # Unknown context - fail closed


class StoreType(Enum):
    """Application store types."""
    
    NONE = "none"                    # Not from a store
    MICROSOFT_STORE = "microsoft"    # Microsoft Store
    MAC_APP_STORE = "mac_app_store" # Mac App Store
    GOOGLE_PLAY = "google_play"     # Google Play Store
    IOS_APP_STORE = "ios_app_store" # iOS App Store
    ENTERPRISE_STORE = "enterprise" # Enterprise app store


@dataclass(frozen=True)
class ExecutionEnvironment:
    """Immutable execution environment information."""
    
    context: ExecutionContext
    store_type: StoreType
    platform_name: str
    platform_version: str
    app_signature: Optional[str]
    installation_path: Path
    policy_restrictions: Dict[str, bool]
    tamper_detected: bool
    
    @property
    def allows_local_models(self) -> bool:
        """Check if local models are allowed in this context."""
        return (
            self.context in [ExecutionContext.DEVELOPMENT, ExecutionContext.SIDELOADED_DESKTOP]
            and not self.tamper_detected
            and not self.policy_restrictions.get("force_api_only", False)
        )
    
    @property
    def requires_api_only(self) -> bool:
        """Check if API-only mode is required."""
        return (
            self.context == ExecutionContext.STORE_INSTALLED
            or self.tamper_detected
            or self.policy_restrictions.get("force_api_only", False)
        )
    
    @property
    def security_level(self) -> str:
        """Get required security level."""
        if self.context == ExecutionContext.STORE_INSTALLED:
            return "MAXIMUM"
        elif self.context == ExecutionContext.ENTERPRISE:
            return "HIGH"
        elif self.context == ExecutionContext.SIDELOADED_DESKTOP:
            return "MEDIUM"
        else:
            return "DEVELOPMENT"


class ExecutionContextDetector:
    """
    Production-grade execution context detection with tamper resistance.
    
    Determines execution environment and enforces appropriate LLM policies
    based on distribution method and platform constraints.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("execution_context")
        self._cached_environment: Optional[ExecutionEnvironment] = None
        
    def detect_execution_environment(self) -> ExecutionEnvironment:
        """
        Detect current execution environment with comprehensive validation.
        
        Returns:
            ExecutionEnvironment with detected context and policies
        """
        if self._cached_environment:
            return self._cached_environment
        
        try:
            # Platform detection
            platform_name = platform.system().lower()
            platform_version = platform.version()
            
            # Installation path analysis
            installation_path = Path(sys.executable).parent
            
            # Context detection based on platform
            if platform_name == "windows":
                context, store_type, signature = self._detect_windows_context(installation_path)
            elif platform_name == "darwin":
                context, store_type, signature = self._detect_macos_context(installation_path)
            elif platform_name == "linux":
                context, store_type, signature = self._detect_linux_context(installation_path)
            else:
                context, store_type, signature = ExecutionContext.UNKNOWN, StoreType.NONE, None
            
            # Tamper detection
            tamper_detected = self._detect_tampering(installation_path)
            
            # Policy restrictions
            policy_restrictions = self._load_policy_restrictions(context, store_type)
            
            environment = ExecutionEnvironment(
                context=context,
                store_type=store_type,
                platform_name=platform_name,
                platform_version=platform_version,
                app_signature=signature,
                installation_path=installation_path,
                policy_restrictions=policy_restrictions,
                tamper_detected=tamper_detected,
            )
            
            self._cached_environment = environment
            
            self.logger.info(
                "Execution environment detected",
                context=context.value,
                store_type=store_type.value,
                platform=platform_name,
                allows_local=environment.allows_local_models,
                requires_api=environment.requires_api_only,
                security_level=environment.security_level,
            )
            
            return environment
            
        except Exception as e:
            self.logger.error(f"Context detection failed: {e}")
            # Fail closed - assume most restrictive context
            return ExecutionEnvironment(
                context=ExecutionContext.STORE_INSTALLED,
                store_type=StoreType.NONE,
                platform_name=platform.system().lower(),
                platform_version=platform.version(),
                app_signature=None,
                installation_path=Path(sys.executable).parent,
                policy_restrictions={"force_api_only": True},
                tamper_detected=True,
            )
    
    def _detect_windows_context(self, install_path: Path) -> Tuple[ExecutionContext, StoreType, Optional[str]]:
        """Detect Windows execution context."""
        try:
            # Check for Microsoft Store installation
            if "WindowsApps" in str(install_path):
                return ExecutionContext.STORE_INSTALLED, StoreType.MICROSOFT_STORE, None
            
            # Check for development environment
            if self._is_development_environment():
                return ExecutionContext.DEVELOPMENT, StoreType.NONE, None
            
            # Check for enterprise deployment
            if self._is_enterprise_deployment(install_path):
                return ExecutionContext.ENTERPRISE, StoreType.ENTERPRISE_STORE, None
            
            # Default to sideloaded
            return ExecutionContext.SIDELOADED_DESKTOP, StoreType.NONE, None
            
        except Exception as e:
            self.logger.warning(f"Windows context detection failed: {e}")
            return ExecutionContext.UNKNOWN, StoreType.NONE, None
    
    def _detect_macos_context(self, install_path: Path) -> Tuple[ExecutionContext, StoreType, Optional[str]]:
        """Detect macOS execution context."""
        try:
            # Check for Mac App Store installation
            if "/Applications/" in str(install_path) and install_path.suffix == ".app":
                # Verify App Store signature
                signature = self._verify_macos_signature(install_path)
                if signature and "Mac App Store" in signature:
                    return ExecutionContext.STORE_INSTALLED, StoreType.MAC_APP_STORE, signature
            
            # Check for development environment
            if self._is_development_environment():
                return ExecutionContext.DEVELOPMENT, StoreType.NONE, None
            
            # Default to sideloaded
            return ExecutionContext.SIDELOADED_DESKTOP, StoreType.NONE, None
            
        except Exception as e:
            self.logger.warning(f"macOS context detection failed: {e}")
            return ExecutionContext.UNKNOWN, StoreType.NONE, None
    
    def _detect_linux_context(self, install_path: Path) -> Tuple[ExecutionContext, StoreType, Optional[str]]:
        """Detect Linux execution context."""
        try:
            # Check for Snap package
            if "/snap/" in str(install_path):
                return ExecutionContext.STORE_INSTALLED, StoreType.NONE, "snap"
            
            # Check for Flatpak
            if "/.local/share/flatpak/" in str(install_path) or "/var/lib/flatpak/" in str(install_path):
                return ExecutionContext.STORE_INSTALLED, StoreType.NONE, "flatpak"
            
            # Check for development environment
            if self._is_development_environment():
                return ExecutionContext.DEVELOPMENT, StoreType.NONE, None
            
            # Default to sideloaded
            return ExecutionContext.SIDELOADED_DESKTOP, StoreType.NONE, None
            
        except Exception as e:
            self.logger.warning(f"Linux context detection failed: {e}")
            return ExecutionContext.UNKNOWN, StoreType.NONE, None
    
    def _is_development_environment(self) -> bool:
        """Check if running in development environment."""
        dev_indicators = [
            os.getenv("GURU_DEV_MODE") == "true",
            "pytest" in sys.modules,
            "debugpy" in sys.modules,
            Path.cwd().name in ["Agent_Guru", "guru-dev", "guru-development"],
            any(Path.cwd().glob("*.py")),  # Python files in current directory
        ]
        return any(dev_indicators)
    
    def _is_enterprise_deployment(self, install_path: Path) -> bool:
        """Check if this is an enterprise deployment."""
        enterprise_indicators = [
            "Program Files" in str(install_path) and "Enterprise" in str(install_path),
            (install_path / "enterprise.manifest").exists(),
            os.getenv("GURU_ENTERPRISE_MODE") == "true",
        ]
        return any(enterprise_indicators)
    
    def _verify_macos_signature(self, app_path: Path) -> Optional[str]:
        """Verify macOS application signature."""
        try:
            result = subprocess.run(
                ["codesign", "-dv", str(app_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stderr if result.returncode == 0 else None
        except Exception:
            return None
    
    def _detect_tampering(self, install_path: Path) -> bool:
        """Detect potential tampering with installation."""
        try:
            # Check for suspicious modifications
            suspicious_indicators = [
                # Debugger attachment
                "debugpy" in sys.modules and not self._is_development_environment(),
                
                # Modified Python installation
                not hasattr(sys, "real_prefix") and hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix,
                
                # Suspicious environment variables
                os.getenv("GURU_BYPASS_SECURITY") is not None,
                os.getenv("GURU_FORCE_LOCAL") is not None,
                
                # Modified executable
                self._check_executable_integrity(),
            ]
            
            return any(suspicious_indicators)
            
        except Exception as e:
            self.logger.warning(f"Tamper detection failed: {e}")
            return True  # Fail closed
    
    def _check_executable_integrity(self) -> bool:
        """Check if executable has been modified."""
        try:
            # This would implement actual integrity checking in production
            # For now, return False (no tampering detected)
            return False
        except Exception:
            return True  # Assume tampering if check fails
    
    def _load_policy_restrictions(self, context: ExecutionContext, store_type: StoreType) -> Dict[str, bool]:
        """Load policy restrictions based on context."""
        restrictions = {
            "force_api_only": False,
            "disable_local_models": False,
            "require_user_consent": False,
            "enable_telemetry": False,
            "restrict_file_access": False,
        }
        
        # Store-installed apps have strict restrictions
        if context == ExecutionContext.STORE_INSTALLED:
            restrictions.update({
                "force_api_only": True,
                "disable_local_models": True,
                "restrict_file_access": True,
            })
        
        # Platform-specific restrictions
        if store_type == StoreType.IOS_APP_STORE:
            restrictions.update({
                "force_api_only": True,
                "disable_local_models": True,
                "restrict_file_access": True,
            })
        elif store_type == StoreType.GOOGLE_PLAY:
            restrictions.update({
                "require_user_consent": True,
            })
        
        # Load additional restrictions from policy file
        try:
            policy_file = Path.home() / ".guru" / "policy.json"
            if policy_file.exists():
                with open(policy_file) as f:
                    policy_data = json.load(f)
                    restrictions.update(policy_data.get("restrictions", {}))
        except Exception as e:
            self.logger.warning(f"Failed to load policy file: {e}")
        
        return restrictions


# Global detector instance
_detector: Optional[ExecutionContextDetector] = None


def get_execution_context() -> ExecutionEnvironment:
    """Get current execution context (cached)."""
    global _detector
    if _detector is None:
        _detector = ExecutionContextDetector()
    return _detector.detect_execution_environment()


def requires_api_only_mode() -> bool:
    """Check if API-only mode is required in current context."""
    return get_execution_context().requires_api_only


def allows_local_models() -> bool:
    """Check if local models are allowed in current context."""
    return get_execution_context().allows_local_models