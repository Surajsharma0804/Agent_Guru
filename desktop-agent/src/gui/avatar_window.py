"""
GURU Avatar Window - Visual Presence

Creates an animated, always-on-top window showing GURU's visual presence
with real-time status, animations, and voice visualization.

Features:
- Animated avatar with multiple states (listening, thinking, speaking, idle)
- Voice waveform visualization during speech
- Status indicators (authority state, system health)
- Transparent/semi-transparent window
- Always-on-top, draggable
- Minimalist, non-intrusive design
- Smooth animations and transitions
"""

import math
import sys
from enum import Enum
from typing import Optional

try:
    from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
    from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class AvatarState(Enum):
    """Visual states for GURU avatar"""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    PROCESSING = "processing"
    ERROR = "error"
    LOCKED = "locked"


class VoiceVisualizer(QWidget):
    """Real-time voice waveform visualizer"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 80)
        self.audio_levels = [0.0] * 50
        self.animation_phase = 0.0
        self.is_active = False
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)  # 20 FPS
    
    def set_active(self, active: bool):
        """Set visualizer active state"""
        self.is_active = active
    
    def update_audio_level(self, level: float):
        """Update audio level (0.0 to 1.0)"""
        self.audio_levels.pop(0)
        self.audio_levels.append(level)
        self.update()
    
    def update_animation(self):
        """Update animation phase"""
        if self.is_active:
            self.animation_phase += 0.1
            if self.animation_phase > 2 * math.pi:
                self.animation_phase = 0.0
            self.update()
    
    def paintEvent(self, event):
        """Paint voice waveform"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        center_y = height // 2
        
        if self.is_active:
            # Active waveform
            gradient = QLinearGradient(0, 0, width, 0)
            gradient.setColorAt(0, QColor(100, 200, 255, 200))
            gradient.setColorAt(0.5, QColor(150, 100, 255, 255))
            gradient.setColorAt(1, QColor(100, 200, 255, 200))
            
            pen = QPen(gradient, 3)
            painter.setPen(pen)
            
            bar_width = width / len(self.audio_levels)
            for i, level in enumerate(self.audio_levels):
                x = i * bar_width
                # Add sine wave animation
                animated_level = level + 0.2 * math.sin(self.animation_phase + i * 0.2)
                bar_height = max(5, int(animated_level * height * 0.8))
                
                painter.drawLine(
                    int(x), center_y - bar_height // 2,
                    int(x), center_y + bar_height // 2
                )
        else:
            # Idle state - subtle pulse
            pen = QPen(QColor(100, 100, 100, 100), 2)
            painter.setPen(pen)
            
            pulse = 0.3 + 0.1 * math.sin(self.animation_phase)
            bar_height = int(pulse * height * 0.3)
            
            for i in range(len(self.audio_levels)):
                x = i * (width / len(self.audio_levels))
                painter.drawLine(
                    int(x), center_y - bar_height // 2,
                    int(x), center_y + bar_height // 2
                )


class AvatarWidget(QWidget):
    """Animated GURU avatar"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.state = AvatarState.IDLE
        self.animation_phase = 0.0
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)  # 20 FPS
    
    def set_state(self, state: AvatarState):
        """Set avatar state"""
        self.state = state
        self.update()
    
    def update_animation(self):
        """Update animation phase"""
        self.animation_phase += 0.1
        if self.animation_phase > 2 * math.pi:
            self.animation_phase = 0.0
        self.update()
    
    def paintEvent(self, event):
        """Paint avatar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        center_x = width // 2
        center_y = height // 2
        
        # State-specific colors
        colors = {
            AvatarState.IDLE: (100, 150, 200),
            AvatarState.LISTENING: (100, 200, 100),
            AvatarState.THINKING: (200, 150, 100),
            AvatarState.SPEAKING: (150, 100, 200),
            AvatarState.PROCESSING: (200, 200, 100),
            AvatarState.ERROR: (200, 100, 100),
            AvatarState.LOCKED: (150, 150, 150)
        }
        
        r, g, b = colors.get(self.state, (100, 150, 200))
        
        # Pulsing circle
        pulse = 1.0 + 0.1 * math.sin(self.animation_phase)
        radius = int(min(width, height) * 0.35 * pulse)
        
        # Outer glow
        for i in range(10):
            alpha = int(50 * (1 - i / 10))
            painter.setPen(QPen(QColor(r, g, b, alpha), 2))
            glow_radius = radius + i * 3
            painter.drawEllipse(
                center_x - glow_radius, center_y - glow_radius,
                glow_radius * 2, glow_radius * 2
            )
        
        # Main circle
        gradient = QLinearGradient(center_x - radius, center_y - radius,
                                   center_x + radius, center_y + radius)
        gradient.setColorAt(0, QColor(r + 50, g + 50, b + 50, 255))
        gradient.setColorAt(1, QColor(r, g, b, 255))
        
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(r + 30, g + 30, b + 30, 255), 3))
        painter.drawEllipse(
            center_x - radius, center_y - radius,
            radius * 2, radius * 2
        )
        
        # State-specific animations
        if self.state == AvatarState.LISTENING:
            # Listening waves
            for i in range(3):
                wave_radius = radius + 20 + i * 15 + int(10 * math.sin(self.animation_phase + i))
                alpha = int(100 * (1 - i / 3))
                painter.setPen(QPen(QColor(100, 200, 100, alpha), 2))
                painter.drawEllipse(
                    center_x - wave_radius, center_y - wave_radius,
                    wave_radius * 2, wave_radius * 2
                )
        
        elif self.state == AvatarState.THINKING:
            # Thinking dots
            for i in range(3):
                dot_y = center_y + int(10 * math.sin(self.animation_phase + i * 0.5))
                dot_x = center_x - 20 + i * 20
                painter.setBrush(QColor(200, 150, 100, 255))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(dot_x - 5, dot_y - 5, 10, 10)
        
        elif self.state == AvatarState.SPEAKING:
            # Speaking waves
            for i in range(5):
                wave_offset = int(15 * math.sin(self.animation_phase + i * 0.3))
                painter.setPen(QPen(QColor(150, 100, 200, 150), 2))
                painter.drawLine(
                    center_x - 40 + i * 20, center_y + wave_offset,
                    center_x - 30 + i * 20, center_y - wave_offset
                )


class GURUAvatarWindow(QMainWindow):
    """
    Main GURU avatar window with visual presence and controls.
    
    Features:
    - Always-on-top, draggable window
    - Animated avatar showing current state
    - Voice waveform visualization
    - Status indicators
    - Quick action buttons
    - Transparent background
    """
    
    # Signals
    voice_button_clicked = pyqtSignal()
    settings_button_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GURU")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Window properties
        self.dragging = False
        self.drag_position = QPoint()
        
        # Setup UI
        self.setup_ui()
        
        # Position window
        self.resize(400, 500)
        self.move_to_corner()
    
    def setup_ui(self):
        """Setup user interface"""
        # Central widget
        central = QWidget()
        central.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 30, 230);
                border-radius: 20px;
            }
        """)
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("GURU")
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Avatar
        self.avatar = AvatarWidget()
        layout.addWidget(self.avatar)
        
        # Status label
        self.status_label = QLabel("Ready to assist")
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 200);
                font-size: 14px;
                background: transparent;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Voice visualizer
        self.visualizer = VoiceVisualizer()
        layout.addWidget(self.visualizer)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.voice_button = QPushButton("🎤 Talk")
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 200, 100, 200);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(120, 220, 120, 255);
            }
            QPushButton:pressed {
                background-color: rgba(80, 180, 80, 255);
            }
        """)
        self.voice_button.clicked.connect(self.voice_button_clicked.emit)
        button_layout.addWidget(self.voice_button)
        
        self.settings_button = QPushButton("⚙️")
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 100, 100, 200);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(120, 120, 120, 255);
            }
        """)
        self.settings_button.clicked.connect(self.settings_button_clicked.emit)
        button_layout.addWidget(self.settings_button)
        
        layout.addLayout(button_layout)
        
        # Close button
        close_button = QPushButton("×")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 100, 100, 200);
                color: white;
                border: none;
                border-radius: 15px;
                padding: 5px;
                font-size: 20px;
                font-weight: bold;
                max-width: 30px;
                max-height: 30px;
            }
            QPushButton:hover {
                background-color: rgba(220, 120, 120, 255);
            }
        """)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
    
    def set_state(self, state: AvatarState):
        """Set avatar state"""
        self.avatar.set_state(state)
        
        # Update status text
        status_texts = {
            AvatarState.IDLE: "Ready to assist",
            AvatarState.LISTENING: "Listening...",
            AvatarState.THINKING: "Thinking...",
            AvatarState.SPEAKING: "Speaking...",
            AvatarState.PROCESSING: "Processing...",
            AvatarState.ERROR: "Error occurred",
            AvatarState.LOCKED: "Locked - Authentication required"
        }
        self.status_label.setText(status_texts.get(state, "Ready"))
    
    def set_visualizer_active(self, active: bool):
        """Set voice visualizer active"""
        self.visualizer.set_active(active)
    
    def update_audio_level(self, level: float):
        """Update audio level visualization"""
        self.visualizer.update_audio_level(level)
    
    def move_to_corner(self):
        """Move window to bottom-right corner"""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.width() - self.width() - 20,
            screen.height() - self.height() - 80
        )
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False


def create_guru_window() -> Optional[GURUAvatarWindow]:
    """
    Factory function to create GURU avatar window.
    
    Returns:
        GURUAvatarWindow instance or None if PyQt6 not available
    """
    if not PYQT_AVAILABLE:
        return None
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = GURUAvatarWindow()
    return window


# Export
__all__ = ['GURUAvatarWindow', 'AvatarState', 'create_guru_window']
