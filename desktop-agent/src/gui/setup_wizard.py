"""
First-Time Setup Wizard

Interactive setup wizard for GURU initial configuration.
Handles permissions, user profile creation, and system preferences.
"""

import sys
from pathlib import Path
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QCheckBox, QComboBox, QTextEdit,
        QMessageBox, QApplication
    )
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QFont
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.user_config import get_config_manager
from src.biometric.providers import BiometricFactor


class WelcomePage(QWizardPage):
    """Welcome page with permissions request"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to GURU")
        self.setSubTitle("Your Personal AI Assistant")
        
        layout = QVBoxLayout()
        
        # Welcome message
        welcome_text = QLabel(
            "GURU is a humanized AI assistant that provides natural voice interaction,\n"
            "intelligent automation, and complete privacy.\n\n"
            "To function properly, GURU needs access to:\n"
            "• Microphone - To hear your voice commands\n"
            "• Speakers - To respond to you vocally\n"
            "• System - To execute commands on your behalf\n\n"
            "All processing happens locally on your machine.\n"
            "No data is sent to external servers."
        )
        welcome_text.setWordWrap(True)
        layout.addWidget(welcome_text)
        
        # Permissions checkboxes
        layout.addSpacing(20)
        
        self.mic_permission = QCheckBox("Grant microphone access")
        self.mic_permission.setChecked(True)
        layout.addWidget(self.mic_permission)
        
        self.speaker_permission = QCheckBox("Grant speaker access")
        self.speaker_permission.setChecked(True)
        layout.addWidget(self.speaker_permission)
        
        self.system_permission = QCheckBox("Grant system control access")
        self.system_permission.setChecked(True)
        layout.addWidget(self.system_permission)
        
        layout.addSpacing(20)
        
        privacy_note = QLabel(
            "Privacy Note: GURU is completely local-first. Your voice data,\n"
            "commands, and personal information never leave your computer."
        )
        privacy_note.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(privacy_note)
        
        self.setLayout(layout)
        
        # Register fields
        self.registerField("mic_permission", self.mic_permission)
        self.registerField("speaker_permission", self.speaker_permission)
        self.registerField("system_permission", self.system_permission)
    
    def validatePage(self):
        """Validate permissions"""
        if not self.mic_permission.isChecked():
            QMessageBox.warning(
                self,
                "Microphone Required",
                "GURU requires microphone access to hear your voice commands.\n"
                "Please grant microphone permission to continue."
            )
            return False
        
        if not self.speaker_permission.isChecked():
            QMessageBox.warning(
                self,
                "Speaker Required",
                "GURU requires speaker access to respond to you vocally.\n"
                "Please grant speaker permission to continue."
            )
            return False
        
        return True


class UserProfilePage(QWizardPage):
    """User profile creation page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Create Your Profile")
        self.setSubTitle("Tell GURU about yourself")
        
        layout = QVBoxLayout()
        
        # Display name
        layout.addWidget(QLabel("What should GURU call you?"))
        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("e.g., Suraj, John, Sarah")
        layout.addWidget(self.display_name)
        
        layout.addSpacing(10)
        
        # Username
        layout.addWidget(QLabel("Username (for system identification):"))
        self.username = QLineEdit()
        self.username.setPlaceholderText("e.g., suraj_kumar")
        layout.addWidget(self.username)
        
        layout.addSpacing(10)
        
        # Password
        layout.addWidget(QLabel("Create a password:"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Enter secure password")
        layout.addWidget(self.password)
        
        layout.addSpacing(5)
        
        layout.addWidget(QLabel("Confirm password:"))
        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirm.setPlaceholderText("Re-enter password")
        layout.addWidget(self.password_confirm)
        
        layout.addSpacing(10)
        
        # Language preference
        layout.addWidget(QLabel("Preferred language:"))
        self.language = QComboBox()
        self.language.addItems([
            "English",
            "Hindi",
            "English + Hindi (Mixed)"
        ])
        layout.addWidget(self.language)
        
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Register fields
        self.registerField("display_name*", self.display_name)
        self.registerField("username*", self.username)
        self.registerField("password*", self.password)
        self.registerField("language", self.language, "currentText")
    
    def validatePage(self):
        """Validate user input"""
        if len(self.display_name.text().strip()) < 2:
            QMessageBox.warning(self, "Invalid Name", "Please enter your name (at least 2 characters).")
            return False
        
        if len(self.username.text().strip()) < 3:
            QMessageBox.warning(self, "Invalid Username", "Username must be at least 3 characters.")
            return False
        
        if len(self.password.text()) < 6:
            QMessageBox.warning(self, "Weak Password", "Password must be at least 6 characters.")
            return False
        
        if self.password.text() != self.password_confirm.text():
            QMessageBox.warning(self, "Password Mismatch", "Passwords do not match. Please try again.")
            return False
        
        return True


class BiometricPage(QWizardPage):
    """Biometric authentication setup page with actual enrollment"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Biometric Authentication (Optional)")
        self.setSubTitle("Add fingerprint or face recognition for quick access")
        
        layout = QVBoxLayout()
        
        info_text = QLabel(
            "You can add biometric authentication for faster and more secure access.\n"
            "This is optional and can be configured later."
        )
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        layout.addSpacing(20)
        
        # Check Windows Hello availability
        self.windows_hello_available = self._check_windows_hello()
        
        if not self.windows_hello_available:
            warning = QLabel(
                "⚠ Windows Hello is not available on this system.\n"
                "Biometric authentication requires Windows 10 (build 1511) or later\n"
                "with Windows Hello configured."
            )
            warning.setStyleSheet("color: #d9534f; font-weight: bold;")
            warning.setWordWrap(True)
            layout.addWidget(warning)
            
            layout.addSpacing(10)
            
            help_text = QLabel(
                "To enable Windows Hello:\n"
                "1. Open Windows Settings\n"
                "2. Go to Accounts → Sign-in options\n"
                "3. Set up Windows Hello Face or Fingerprint"
            )
            help_text.setStyleSheet("color: #666;")
            layout.addWidget(help_text)
        else:
            # Biometric options
            self.enable_biometric = QCheckBox("Enable biometric authentication")
            layout.addWidget(self.enable_biometric)
            
            layout.addSpacing(10)
            
            # Check available factors
            available_factors = self._get_available_factors()
            
            # Import BiometricFactor for comparison
            from src.authority.state import BiometricFactor
            
            # Display detected hardware
            hardware_status = QLabel("Detected biometric hardware:")
            hardware_status.setStyleSheet("font-weight: bold;")
            layout.addWidget(hardware_status)
            
            layout.addSpacing(5)
            
            self.fingerprint = QCheckBox("Use fingerprint (Windows Hello)")
            self.fingerprint.setEnabled(False)
            if BiometricFactor.FINGERPRINT in available_factors:
                self.fingerprint.setText("✓ Use fingerprint (Windows Hello) - DETECTED")
                self.fingerprint.setStyleSheet("color: #5cb85c;")
                self.fingerprint.setToolTip("Fingerprint sensor detected and configured")
            else:
                self.fingerprint.setText("✗ Use fingerprint (Windows Hello) - NOT AVAILABLE")
                self.fingerprint.setStyleSheet("color: #999;")
                self.fingerprint.setToolTip("No fingerprint sensor detected or not configured")
            layout.addWidget(self.fingerprint)
            
            self.face_recognition = QCheckBox("Use face recognition (Windows Hello)")
            self.face_recognition.setEnabled(False)
            if BiometricFactor.FACE in available_factors:
                self.face_recognition.setText("✓ Use face recognition (Windows Hello) - DETECTED")
                self.face_recognition.setStyleSheet("color: #5cb85c;")
                self.face_recognition.setToolTip("Face recognition camera detected and configured")
            else:
                self.face_recognition.setText("✗ Use face recognition (Windows Hello) - NOT AVAILABLE")
                self.face_recognition.setStyleSheet("color: #999;")
                self.face_recognition.setToolTip("No face recognition camera detected or not configured")
            layout.addWidget(self.face_recognition)
            
            # Enable/disable based on main checkbox
            self.enable_biometric.stateChanged.connect(self._toggle_biometric_options)
            
            layout.addSpacing(10)
            
            # Enrollment button
            self.enroll_button = QPushButton("Test Biometric Authentication")
            self.enroll_button.setEnabled(False)
            self.enroll_button.clicked.connect(self._test_biometric)
            layout.addWidget(self.enroll_button)
            
            self.enable_biometric.stateChanged.connect(
                lambda state: self.enroll_button.setEnabled(state == Qt.CheckState.Checked.value)
            )
            
            layout.addSpacing(10)
            
            self.status_label = QLabel("")
            self.status_label.setWordWrap(True)
            layout.addWidget(self.status_label)
        
        layout.addSpacing(20)
        
        note = QLabel(
            "Note: GURU uses Windows Hello for biometric authentication.\n"
            "Your biometric data is stored securely by Windows and never\n"
            "leaves your device. GURU only receives authentication results."
        )
        note.setStyleSheet("color: #666; font-style: italic;")
        note.setWordWrap(True)
        layout.addWidget(note)
        
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Register fields
        if self.windows_hello_available:
            self.registerField("enable_biometric", self.enable_biometric)
            self.registerField("fingerprint", self.fingerprint)
            self.registerField("face_recognition", self.face_recognition)
        else:
            # Register dummy fields if Windows Hello not available
            dummy_checkbox = QCheckBox()
            dummy_checkbox.setVisible(False)
            dummy_checkbox.setChecked(False)
            layout.addWidget(dummy_checkbox)
            self.registerField("enable_biometric", dummy_checkbox)
            self.registerField("fingerprint", dummy_checkbox)
            self.registerField("face_recognition", dummy_checkbox)
    
    def _check_windows_hello(self) -> bool:
        """Check if Windows Hello is available"""
        try:
            from src.biometric.providers import WindowsHelloProvider, BiometricProviderConfig
            
            config = BiometricProviderConfig()
            provider = WindowsHelloProvider(config)
            
            return provider.is_available()
        except Exception as e:
            print(f"Error checking Windows Hello: {e}")
            return False
    
    def _get_available_factors(self):
        """Get available biometric factors"""
        try:
            from src.biometric.providers import WindowsHelloProvider, BiometricProviderConfig
            from src.authority.state import BiometricFactor
            
            config = BiometricProviderConfig()
            provider = WindowsHelloProvider(config)
            
            return provider.get_supported_factors()
        except Exception as e:
            print(f"Error getting biometric factors: {e}")
            return []
    
    def _test_biometric(self):
        """Test biometric authentication"""
        self.status_label.setText("Testing biometric authentication...")
        self.status_label.setStyleSheet("color: #5bc0de;")
        
        try:
            from src.biometric.providers import WindowsHelloProvider, BiometricProviderConfig
            from src.authority.state import BiometricFactor
            import asyncio
            
            config = BiometricProviderConfig()
            provider = WindowsHelloProvider(config)
            
            # Determine which factor to test
            factor = None
            if self.fingerprint.isChecked() and self.fingerprint.isEnabled():
                factor = BiometricFactor.FINGERPRINT
            elif self.face_recognition.isChecked() and self.face_recognition.isEnabled():
                factor = BiometricFactor.FACE
            
            if not factor:
                self.status_label.setText("Please select a biometric method to test.")
                self.status_label.setStyleSheet("color: #f0ad4e;")
                return
            
            # Run async verification
            async def verify():
                return await provider.enforce_biometric_verification_boundary(factor, timeout_seconds=10)
            
            # Create event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(verify())
            
            if result.success:
                self.status_label.setText(
                    f"✓ Biometric authentication successful!\n"
                    f"Confidence: {result.confidence_score:.0%}"
                )
                self.status_label.setStyleSheet("color: #5cb85c; font-weight: bold;")
            else:
                self.status_label.setText(
                    f"✗ Biometric authentication failed.\n"
                    f"Error: {result.failure_reason or 'Unknown error'}"
                )
                self.status_label.setStyleSheet("color: #d9534f;")
        
        except Exception as e:
            self.status_label.setText(
                f"✗ Error testing biometric authentication:\n{str(e)}"
            )
            self.status_label.setStyleSheet("color: #d9534f;")
    
    def _toggle_biometric_options(self, state):
        """Toggle biometric options"""
        if not self.windows_hello_available:
            return
        
        enabled = state == Qt.CheckState.Checked.value
        
        # Only enable options that have available hardware
        available_factors = self._get_available_factors()
        
        from src.authority.state import BiometricFactor
        
        if BiometricFactor.FINGERPRINT in available_factors:
            self.fingerprint.setEnabled(enabled)
        
        if BiometricFactor.FACE in available_factors:
            self.face_recognition.setEnabled(enabled)


class PreferencesPage(QWizardPage):
    """System preferences page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("System Preferences")
        self.setSubTitle("Configure how GURU behaves")
        
        layout = QVBoxLayout()
        
        # Auto-start
        self.auto_start = QCheckBox("Start GURU automatically when Windows starts")
        self.auto_start.setChecked(True)
        layout.addWidget(self.auto_start)
        
        layout.addSpacing(10)
        
        # Hidden mode
        self.hidden_mode = QCheckBox("Enable hidden mode (GURU can be hidden and awakened)")
        self.hidden_mode.setChecked(True)
        layout.addWidget(self.hidden_mode)
        
        layout.addSpacing(10)
        
        # Voice always on
        self.voice_always_on = QCheckBox("Keep voice recognition always active")
        self.voice_always_on.setChecked(True)
        layout.addWidget(self.voice_always_on)
        
        layout.addSpacing(20)
        
        # Wake phrases
        layout.addWidget(QLabel("Wake phrases (one per line):"))
        self.wake_phrases = QTextEdit()
        self.wake_phrases.setPlainText(
            "hey guru\n"
            "hello guru\n"
            "guru where are you\n"
            "guru tum kaha ho"
        )
        self.wake_phrases.setMaximumHeight(100)
        layout.addWidget(self.wake_phrases)
        
        layout.addSpacing(10)
        
        info = QLabel(
            "You can say any of these phrases to activate GURU from hidden mode."
        )
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Register fields
        self.registerField("auto_start", self.auto_start)
        self.registerField("hidden_mode", self.hidden_mode)
        self.registerField("voice_always_on", self.voice_always_on)


class CompletionPage(QWizardPage):
    """Setup completion page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Setup Complete!")
        self.setSubTitle("GURU is ready to assist you")
        
        layout = QVBoxLayout()
        
        completion_text = QLabel(
            "Congratulations! GURU has been configured successfully.\n\n"
            "To start using GURU:\n"
            "• Say 'Hey GURU' to activate voice commands\n"
            "• Say 'GURU where are you?' to wake from hidden mode\n"
            "• Click the avatar window to interact manually\n\n"
            "GURU will now start and greet you by name.\n\n"
            "You can change these settings anytime in the GURU settings panel."
        )
        completion_text.setWordWrap(True)
        layout.addWidget(completion_text)
        
        layout.addStretch()
        
        self.setLayout(layout)


class SetupWizard(QWizard):
    """
    Production-grade setup wizard for GURU.
    
    Handles:
    - Permission requests
    - User profile creation
    - Biometric setup
    - System preferences
    - Configuration persistence
    """
    
    setup_complete = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("GURU Setup Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.setMinimumSize(600, 500)
        
        # Add pages
        self.addPage(WelcomePage())
        self.addPage(UserProfilePage())
        self.addPage(BiometricPage())
        self.addPage(PreferencesPage())
        self.addPage(CompletionPage())
        
        # Connect finish button
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self._on_finish)
    
    def _on_finish(self):
        """Handle setup completion"""
        # Collect all data
        setup_data = {
            'display_name': self.field('display_name'),
            'username': self.field('username'),
            'password': self.field('password'),
            'language': self.field('language'),
            'auto_start': self.field('auto_start'),
            'hidden_mode': self.field('hidden_mode'),
            'voice_always_on': self.field('voice_always_on'),
            'enable_biometric': self.field('enable_biometric'),
            'fingerprint': self.field('fingerprint'),
            'face_recognition': self.field('face_recognition'),
        }
        
        # Create user profile
        config_manager = get_config_manager()
        
        # Map language
        language_map = {
            "English": "en",
            "Hindi": "hi",
            "English + Hindi (Mixed)": "en-hi"
        }
        
        profile = config_manager.create_user_profile(
            user_name=setup_data['username'],
            display_name=setup_data['display_name'],
            password=setup_data['password'],
            preferred_language=language_map.get(setup_data['language'], "en")
        )
        
        # Update preferences
        config_manager.update_preferences(
            auto_start=setup_data['auto_start'],
            hidden_mode_enabled=setup_data['hidden_mode'],
            voice_enabled=setup_data['voice_always_on'],
            biometric_enabled=setup_data['enable_biometric']
        )
        
        # Mark setup as complete
        try:
            from src.config.first_run_detector import mark_setup_complete
            mark_setup_complete()
        except Exception as e:
            print(f"[WARNING] Failed to mark setup complete: {e}")
        
        # Emit completion signal
        self.setup_complete.emit(setup_data)


def run_setup_wizard() -> Optional[dict]:
    """Run setup wizard and return configuration"""
    if not PYQT_AVAILABLE:
        print("ERROR: PyQt6 required for setup wizard")
        return None
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    wizard = SetupWizard()
    
    setup_data = None
    
    def on_complete(data):
        nonlocal setup_data
        setup_data = data
    
    wizard.setup_complete.connect(on_complete)
    
    result = wizard.exec()
    
    if result == QWizard.DialogCode.Accepted:
        return setup_data
    
    return None


if __name__ == "__main__":
    setup_data = run_setup_wizard()
    if setup_data:
        print("Setup completed successfully!")
        print(f"User: {setup_data['display_name']}")
    else:
        print("Setup cancelled")
