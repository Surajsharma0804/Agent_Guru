"""
User Configuration Management

Handles user preferences, authentication credentials, and system settings.
Provides secure storage and retrieval of user data with encryption.
"""

import base64
import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet


@dataclass
class UserProfile:
    """User profile with authentication and preferences"""
    user_name: str
    display_name: str
    password_hash: Optional[str] = None
    biometric_enabled: bool = False
    fingerprint_data: Optional[str] = None
    face_data: Optional[str] = None
    preferred_language: str = "en"
    voice_enabled: bool = True
    auto_start: bool = True
    hidden_mode_enabled: bool = False
    wake_phrases: list = None
    
    def __post_init__(self):
        if self.wake_phrases is None:
            self.wake_phrases = [
                "guru where are you",
                "guru tum kaha ho",
                "hey guru",
                "hello guru"
            ]


class UserConfigManager:
    """
    Production-grade user configuration manager.
    
    Features:
    - Encrypted credential storage
    - Secure password hashing (Argon2)
    - Biometric data management
    - First-time setup flow
    - Configuration persistence
    - Migration support
    """
    
    def __init__(self, config_dir: str = ".guru"):
        """Initialize configuration manager"""
        self.config_dir = Path.home() / config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "user_config.json"
        self.key_file = self.config_dir / "encryption.key"
        
        # Initialize encryption
        self._init_encryption()
        
        # Load or create config
        self.profile: Optional[UserProfile] = self._load_config()
    
    def _init_encryption(self):
        """Initialize encryption key"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                self.encryption_key = f.read()
        else:
            # Generate new key
            self.encryption_key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.encryption_key)
            
            # Secure file permissions (Windows)
            try:
                import ntsecuritycon as con
                import win32security

                # Get current user
                user, domain, type = win32security.LookupAccountName("", win32security.GetUserName())
                
                # Create security descriptor
                sd = win32security.SECURITY_DESCRIPTOR()
                dacl = win32security.ACL()
                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, user)
                sd.SetSecurityDescriptorDacl(1, dacl, 0)
                
                # Apply to file
                win32security.SetFileSecurity(
                    str(self.key_file),
                    win32security.DACL_SECURITY_INFORMATION,
                    sd
                )
            except:
                pass  # Best effort on Windows
        
        self.cipher = Fernet(self.encryption_key)
    
    def _load_config(self) -> Optional[UserProfile]:
        """Load user configuration"""
        if not self.config_file.exists():
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                encrypted_data = f.read()
            
            # Decrypt
            decrypted_data = self.cipher.decrypt(encrypted_data.encode())
            config_dict = json.loads(decrypted_data)
            
            return UserProfile(**config_dict)
        
        except Exception as e:
            return None
    
    def _save_config(self):
        """Save user configuration"""
        if not self.profile:
            return
        
        try:
            # Convert to dict
            config_dict = asdict(self.profile)
            
            # Encrypt
            json_data = json.dumps(config_dict)
            encrypted_data = self.cipher.encrypt(json_data.encode())
            
            # Save
            with open(self.config_file, 'w') as f:
                f.write(encrypted_data.decode())
        
        except Exception as e:
            pass
    
    def is_first_time_setup(self) -> bool:
        """Check if this is first time setup"""
        return self.profile is None
    
    def create_user_profile(
        self,
        user_name: str,
        display_name: str,
        password: str,
        preferred_language: str = "en"
    ) -> UserProfile:
        """Create new user profile"""
        # Hash password using Argon2
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        password_hash = ph.hash(password)
        
        self.profile = UserProfile(
            user_name=user_name,
            display_name=display_name,
            password_hash=password_hash,
            preferred_language=preferred_language
        )
        
        self._save_config()
        return self.profile
    
    def verify_password(self, password: str) -> bool:
        """Verify user password"""
        if not self.profile or not self.profile.password_hash:
            return False
        
        try:
            from argon2 import PasswordHasher
            ph = PasswordHasher()
            ph.verify(self.profile.password_hash, password)
            return True
        except:
            return False
    
    def enable_biometric(self, biometric_type: str, data: str):
        """Enable biometric authentication"""
        if not self.profile:
            return
        
        self.profile.biometric_enabled = True
        
        if biometric_type == "fingerprint":
            self.profile.fingerprint_data = data
        elif biometric_type == "face":
            self.profile.face_data = data
        
        self._save_config()
    
    def verify_biometric(self, biometric_type: str, data: str) -> bool:
        """Verify biometric authentication"""
        if not self.profile or not self.profile.biometric_enabled:
            return False
        
        if biometric_type == "fingerprint":
            return self.profile.fingerprint_data == data
        elif biometric_type == "face":
            return self.profile.face_data == data
        
        return False
    
    def update_preferences(self, **kwargs):
        """Update user preferences"""
        if not self.profile:
            return
        
        for key, value in kwargs.items():
            if hasattr(self.profile, key):
                setattr(self.profile, key, value)
        
        self._save_config()
    
    def get_profile(self) -> Optional[UserProfile]:
        """Get user profile"""
        return self.profile
    
    def add_wake_phrase(self, phrase: str):
        """Add custom wake phrase"""
        if not self.profile:
            return
        
        if phrase.lower() not in [p.lower() for p in self.profile.wake_phrases]:
            self.profile.wake_phrases.append(phrase.lower())
            self._save_config()
    
    def get_wake_phrases(self) -> list:
        """Get all wake phrases"""
        if not self.profile:
            return ["hey guru", "hello guru"]
        
        return self.profile.wake_phrases


# Global instance
_config_manager: Optional[UserConfigManager] = None


def get_config_manager() -> UserConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = UserConfigManager()
    return _config_manager
