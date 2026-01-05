"""
GURU Secure Device Pairing Module

This module implements cryptographically secure device pairing using QR codes
and asymmetric key exchange. It provides the foundation for establishing
trusted communication channels between GURU desktop and mobile agents.

Security Features:
- ECDSA-P256 key pair generation
- Cryptographically secure pairing tokens
- Device fingerprint binding
- Token expiration and replay protection
- Physical presence verification requirements

All pairing operations require physical access to both devices and implement
defense-in-depth security measures to prevent unauthorized device pairing.
"""

from .qr_pairing import QRPairingManager, PairingToken, PairingResult
from .key_exchange import KeyExchangeManager, DeviceKeyPair, KeyExchangeResult
from .device_registry import DeviceRegistry, DeviceIdentity, TrustedDevice

__all__ = [
    "QRPairingManager",
    "PairingToken", 
    "PairingResult",
    "KeyExchangeManager",
    "DeviceKeyPair",
    "KeyExchangeResult", 
    "DeviceRegistry",
    "DeviceIdentity",
    "TrustedDevice"
]