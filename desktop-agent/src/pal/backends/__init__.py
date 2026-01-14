"""
Platform-specific backend implementations.

This package contains concrete implementations of PAL interfaces for each
supported platform:
    - Windows (full desktop control)
    - macOS (full desktop control with permissions)
    - Android (partial automation via Accessibility)
    - iOS (command-limited, no system automation)

CRITICAL RULES:
1. Backend implementations MUST implement ALL interface methods
2. Backend implementations MUST maintain security invariants
3. Backend implementations MUST declare capability limitations
4. Backend implementations MUST log all operations for audit

Directory Structure:
    backends/
        windows/        # Windows 10/11 implementations
        macos/          # macOS implementations
        android/        # Android implementations
        ios/            # iOS implementations
"""

__all__ = []
