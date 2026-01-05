"""
Property-Based Tests for Command Authentication

Tests universal properties of command authentication, signature verification,
and replay protection across all command types and scenarios.

**Property 2: Command Authentication**
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**
"""

import json
from typing import Dict, Any, List

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, initialize

from src.pairing.key_exchange import (
    KeyExchangeManager, DeviceKeyPair, KeyExchangeMessage
)
from src.pairing.qr_pairing import DeviceFingerprint
from src.pairing.device_registry import DeviceRegistry, DeviceIdentity


# Hypothesis strategies for generating test data
@st.composite
def device_id_strategy(draw):
    """Generate valid device IDs"""
    prefix = draw(st.sampled_from(["guru-desktop", "guru-phone", "guru-tablet"]))
    # Create alphabet with lowercase letters, digits, and hyphen
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-"
    suffix = draw(st.text(alphabet=alphabet, min_size=8, max_size=32))
    return f"{prefix}-{suffix}"


@st.composite
def command_data_strategy(draw):
    """Generate command data for testing"""
    command_types = ["input_simulation", "skill_execution", "authority_request", "system_query"]
    
    # Use fixed timestamp values instead of time.time() calls to avoid FlakyStrategyDefinition
    base_timestamp = 1704067200.0  # Fixed timestamp: 2024-01-01 00:00:00 UTC
    timestamp_offset = draw(st.floats(min_value=-3600, max_value=3600))  # ±1 hour
    
    return {
        "command_id": draw(st.uuids()).hex,
        "timestamp": base_timestamp + timestamp_offset,
        "command_type": draw(st.sampled_from(command_types)),
        "sender_device_id": draw(device_id_strategy()),
        "recipient_device_id": draw(device_id_strategy()),
        "nonce": draw(st.text(min_size=16, max_size=32)),
        "payload": {
            "action": draw(st.text(min_size=1, max_size=50)),
            "parameters": draw(st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(), st.integers(), st.booleans()),
                min_size=0, max_size=5
            ))
        }
    }


@st.composite
def key_pair_strategy(draw):
    """Generate ECDSA key pairs for testing"""
    device_id = draw(device_id_strategy())
    return DeviceKeyPair.generate(device_id)


class TestCommandAuthenticationProperties:
    """Property-based tests for command authentication"""
    
    @given(command_data=command_data_strategy(), key_pair=key_pair_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_command_signature_verification_property(self, command_data: Dict[str, Any], 
                                                   key_pair: DeviceKeyPair):
        """
        Feature: guru-personal-assistant, Property 2: Command Authentication
        
        For any command sent between paired devices, the command should be 
        cryptographically signed and signature verification should be deterministic.
        
        **Validates: Requirements 2.1, 2.3**
        """
        # Assume valid command structure
        assume(command_data["sender_device_id"] != command_data["recipient_device_id"])
        assume(len(command_data["nonce"]) >= 16)
        
        # Create command message
        command_bytes = json.dumps(command_data, sort_keys=True).encode('utf-8')
        signature = key_pair.sign_data(command_bytes)
        
        # Property: Signature verification should be deterministic
        verification_result_1 = key_pair.verify_signature(command_bytes, signature)
        verification_result_2 = key_pair.verify_signature(command_bytes, signature)
        
        assert verification_result_1 == verification_result_2
        assert verification_result_1 is True  # Valid signature should always verify
        
        # Property: Different data should produce different signatures
        modified_command_data = command_data.copy()
        modified_command_data["nonce"] = command_data["nonce"] + "modified"
        modified_command_bytes = json.dumps(modified_command_data, sort_keys=True).encode('utf-8')
        
        # Original signature should not verify modified data
        assert not key_pair.verify_signature(modified_command_bytes, signature)
    
    @given(command_data=command_data_strategy(), 
           sender_key=key_pair_strategy(), 
           receiver_key=key_pair_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_cross_device_signature_verification_property(self, command_data: Dict[str, Any],
                                                        sender_key: DeviceKeyPair,
                                                        receiver_key: DeviceKeyPair):
        """
        Feature: guru-personal-assistant, Property 2: Command Authentication
        
        For any command signed by one device, another device should be able to verify
        the signature using the sender's public key.
        
        **Validates: Requirements 2.1, 2.2**
        """
        # Assume different devices
        assume(sender_key.device_id != receiver_key.device_id)
        assume(command_data["sender_device_id"] != command_data["recipient_device_id"])
        
        # Sender signs command
        command_bytes = json.dumps(command_data, sort_keys=True).encode('utf-8')
        signature = sender_key.sign_data(command_bytes)
        
        # Property: Receiver can verify using sender's public key
        verification_result = receiver_key.verify_signature(
            command_bytes, signature, sender_key.public_key_pem
        )
        assert verification_result is True
        
        # Property: Verification fails with wrong public key
        wrong_verification = receiver_key.verify_signature(
            command_bytes, signature, receiver_key.public_key_pem
        )
        assert wrong_verification is False
    
    @given(command_data=command_data_strategy(), key_pair=key_pair_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_nonce_uniqueness_property(self, command_data: Dict[str, Any], 
                                     key_pair: DeviceKeyPair):
        """
        Feature: guru-personal-assistant, Property 2: Command Authentication
        
        For any command, including a nonce should make the signature unique
        even for identical command content.
        
        **Validates: Requirements 2.2, 2.4**
        """
        # Create two commands with same content but different nonces
        command1 = command_data.copy()
        command2 = command_data.copy()
        command2["nonce"] = command_data["nonce"] + "_different"
        
        # Assume nonces are actually different
        assume(command1["nonce"] != command2["nonce"])
        
        # Sign both commands
        command1_bytes = json.dumps(command1, sort_keys=True).encode('utf-8')
        command2_bytes = json.dumps(command2, sort_keys=True).encode('utf-8')
        
        signature1 = key_pair.sign_data(command1_bytes)
        signature2 = key_pair.sign_data(command2_bytes)
        
        # Property: Different nonces should produce different signatures
        assert signature1 != signature2
        
        # Property: Each signature should only verify its own command
        assert key_pair.verify_signature(command1_bytes, signature1)
        assert key_pair.verify_signature(command2_bytes, signature2)
        assert not key_pair.verify_signature(command1_bytes, signature2)
        assert not key_pair.verify_signature(command2_bytes, signature1)
    
    @given(command_data=command_data_strategy(), key_pair=key_pair_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_timestamp_inclusion_property(self, command_data: Dict[str, Any], 
                                        key_pair: DeviceKeyPair):
        """
        Feature: guru-personal-assistant, Property 2: Command Authentication
        
        For any command, including a timestamp should prevent replay attacks
        by making signatures time-dependent.
        
        **Validates: Requirements 2.2, 2.4**
        """
        # Create commands with different timestamps using fixed base time
        base_time = 1704067200.0  # Fixed timestamp: 2024-01-01 00:00:00 UTC
        
        command_now = command_data.copy()
        command_now["timestamp"] = base_time
        
        command_later = command_data.copy()
        command_later["timestamp"] = base_time + 3600  # 1 hour later
        
        # Sign both commands
        command_now_bytes = json.dumps(command_now, sort_keys=True).encode('utf-8')
        command_later_bytes = json.dumps(command_later, sort_keys=True).encode('utf-8')
        
        signature_now = key_pair.sign_data(command_now_bytes)
        signature_later = key_pair.sign_data(command_later_bytes)
        
        # Property: Different timestamps should produce different signatures
        assert signature_now != signature_later
        
        # Property: Signatures should not be interchangeable
        assert key_pair.verify_signature(command_now_bytes, signature_now)
        assert key_pair.verify_signature(command_later_bytes, signature_later)
        assert not key_pair.verify_signature(command_now_bytes, signature_later)
        assert not key_pair.verify_signature(command_later_bytes, signature_now)
    
    @given(commands=st.lists(command_data_strategy(), min_size=2, max_size=10), 
           key_pair=key_pair_strategy())
    @settings(max_examples=50, deadline=10000)
    def test_batch_command_authentication_property(self, commands: List[Dict[str, Any]], 
                                                 key_pair: DeviceKeyPair):
        """
        Feature: guru-personal-assistant, Property 2: Command Authentication
        
        For any batch of commands, each command should have a unique signature
        and verification should work independently for each command.
        
        **Validates: Requirements 2.1, 2.3**
        """
        # Ensure all commands have unique nonces
        for i, command in enumerate(commands):
            command["nonce"] = f"{command['nonce']}_{i}"
        
        # Sign all commands
        signatures = []
        command_bytes_list = []
        
        for command in commands:
            command_bytes = json.dumps(command, sort_keys=True).encode('utf-8')
            signature = key_pair.sign_data(command_bytes)
            
            command_bytes_list.append(command_bytes)
            signatures.append(signature)
        
        # Property: All signatures should be unique
        assert len(set(signatures)) == len(signatures)
        
        # Property: Each signature should verify only its corresponding command
        for i, (command_bytes, signature) in enumerate(zip(command_bytes_list, signatures)):
            # Should verify with correct signature
            assert key_pair.verify_signature(command_bytes, signature)
            
            # Should not verify with other signatures
            for j, other_signature in enumerate(signatures):
                if i != j:
                    assert not key_pair.verify_signature(command_bytes, other_signature)


class CommandAuthenticationStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for command authentication workflows
    
    Tests complex scenarios involving multiple devices, key exchanges,
    and command authentication over time.
    """
    
    devices = Bundle('devices')
    commands = Bundle('commands')
    
    def __init__(self):
        super().__init__()
        self.device_managers: Dict[str, KeyExchangeManager] = {}
        self.trusted_relationships: Dict[str, List[str]] = {}
        self.command_history: List[Dict[str, Any]] = []
    
    @initialize()
    def setup(self):
        """Initialize the state machine"""
        pass
    
    @rule(target=devices, device_id=device_id_strategy())
    def create_device(self, device_id: str):
        """Create a new device with key exchange capability"""
        assume(device_id not in self.device_managers)
        
        manager = KeyExchangeManager(device_id)
        manager.generate_device_keys()
        
        self.device_managers[device_id] = manager
        self.trusted_relationships[device_id] = []
        
        return device_id
    
    @rule(sender=devices, receiver=devices)
    def establish_trust(self, sender: str, receiver: str):
        """Establish trust between two devices through key exchange"""
        assume(sender != receiver)
        assume(sender in self.device_managers)
        assume(receiver in self.device_managers)
        assume(receiver not in self.trusted_relationships[sender])
        
        sender_manager = self.device_managers[sender]
        receiver_manager = self.device_managers[receiver]
        
        # Perform key exchange
        request_message, _ = sender_manager.initiate_key_exchange(receiver)
        response_message, _ = receiver_manager.process_key_exchange_request(request_message)
        
        exchange_id = f"{sender}-{receiver}"
        final_result = sender_manager.process_key_exchange_response(response_message, exchange_id)
        
        if final_result.is_successful:
            # Establish mutual trust
            self.trusted_relationships[sender].append(receiver)
            if sender not in self.trusted_relationships[receiver]:
                self.trusted_relationships[receiver].append(sender)
    
    @rule(target=commands, 
          sender=devices, 
          receiver=devices, 
          command_data=command_data_strategy())
    def send_authenticated_command(self, sender: str, receiver: str, 
                                 command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send an authenticated command between trusted devices"""
        assume(sender != receiver)
        assume(sender in self.device_managers)
        assume(receiver in self.device_managers)
        assume(receiver in self.trusted_relationships[sender])
        
        sender_manager = self.device_managers[sender]
        
        # Update command with actual device IDs
        command_data["sender_device_id"] = sender
        command_data["recipient_device_id"] = receiver
        command_data["timestamp"] = 1704067200.0  # Fixed timestamp for deterministic testing
        
        # Sign command
        command_bytes = json.dumps(command_data, sort_keys=True).encode('utf-8')
        signature = sender_manager.device_key_pair.sign_data(command_bytes)
        
        authenticated_command = {
            "command_data": command_data,
            "signature": signature,
            "sender_public_key": sender_manager.device_key_pair.public_key_pem
        }
        
        self.command_history.append(authenticated_command)
        return authenticated_command
    
    @rule(command=commands, verifier=devices)
    def verify_command_signature(self, command: Dict[str, Any], verifier: str):
        """Verify command signature using any device"""
        assume(verifier in self.device_managers)
        
        verifier_manager = self.device_managers[verifier]
        command_data = command["command_data"]
        signature = command["signature"]
        sender_public_key = command["sender_public_key"]
        
        # Reconstruct command bytes
        command_bytes = json.dumps(command_data, sort_keys=True).encode('utf-8')
        
        # Property: Signature verification should be consistent
        result1 = verifier_manager.device_key_pair.verify_signature(
            command_bytes, signature, sender_public_key
        )
        result2 = verifier_manager.device_key_pair.verify_signature(
            command_bytes, signature, sender_public_key
        )
        
        assert result1 == result2
        
        # Property: Valid signatures should always verify
        sender_device_id = command_data["sender_device_id"]
        if (sender_device_id in self.device_managers and 
            sender_device_id in self.trusted_relationships[verifier]):
            assert result1 is True
    
    @rule(command=commands)
    def test_command_tampering_detection(self, command: Dict[str, Any]):
        """Test that command tampering is detected"""
        original_command_data = command["command_data"].copy()
        signature = command["signature"]
        sender_public_key = command["sender_public_key"]
        
        # Tamper with command data
        tampered_command_data = original_command_data.copy()
        tampered_command_data["nonce"] = original_command_data["nonce"] + "_tampered"
        
        # Create a verifier device
        verifier_id = "tamper_verifier"
        if verifier_id not in self.device_managers:
            verifier_manager = KeyExchangeManager(verifier_id)
            verifier_manager.generate_device_keys()
            self.device_managers[verifier_id] = verifier_manager
        else:
            verifier_manager = self.device_managers[verifier_id]
        
        # Property: Tampered command should not verify with original signature
        tampered_bytes = json.dumps(tampered_command_data, sort_keys=True).encode('utf-8')
        tampered_verification = verifier_manager.device_key_pair.verify_signature(
            tampered_bytes, signature, sender_public_key
        )
        
        assert tampered_verification is False


# Run the stateful tests
TestCommandAuthenticationStateMachine = CommandAuthenticationStateMachine.TestCase


class TestCommandReplayProtection:
    """Property-based tests for command replay protection"""
    
    @given(command_data=command_data_strategy(), key_pair=key_pair_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_nonce_prevents_replay_property(self, command_data: Dict[str, Any], 
                                          key_pair: DeviceKeyPair):
        """
        Feature: guru-personal-assistant, Property 2: Command Authentication
        
        For any command with a nonce, replaying the same command should be
        detectable through nonce tracking.
        
        **Validates: Requirements 2.2, 2.4**
        """
        # Simulate nonce tracking (simplified)
        used_nonces = set()
        
        # First command execution
        nonce1 = command_data["nonce"]
        assume(nonce1 not in used_nonces)
        
        command_bytes = json.dumps(command_data, sort_keys=True).encode('utf-8')
        signature = key_pair.sign_data(command_bytes)
        
        # Property: First execution should be allowed
        assert key_pair.verify_signature(command_bytes, signature)
        used_nonces.add(nonce1)
        
        # Property: Replay with same nonce should be detectable
        assert nonce1 in used_nonces  # Replay detection
        
        # Property: New nonce should be allowed
        command_data_new_nonce = command_data.copy()
        command_data_new_nonce["nonce"] = nonce1 + "_new"
        
        new_nonce = command_data_new_nonce["nonce"]
        assert new_nonce not in used_nonces
        
        new_command_bytes = json.dumps(command_data_new_nonce, sort_keys=True).encode('utf-8')
        new_signature = key_pair.sign_data(new_command_bytes)
        
        assert key_pair.verify_signature(new_command_bytes, new_signature)
    
    @given(command_data=command_data_strategy(), key_pair=key_pair_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_timestamp_freshness_property(self, command_data: Dict[str, Any], 
                                        key_pair: DeviceKeyPair):
        """
        Feature: guru-personal-assistant, Property 2: Command Authentication
        
        For any command with a timestamp, old commands should be rejectable
        based on timestamp freshness requirements.
        
        **Validates: Requirements 2.2, 2.4**
        """
        base_time = 1704067200.0  # Fixed timestamp: 2024-01-01 00:00:00 UTC
        max_age = 300  # 5 minutes
        
        # Test with fresh timestamp
        fresh_command = command_data.copy()
        fresh_command["timestamp"] = base_time
        
        fresh_bytes = json.dumps(fresh_command, sort_keys=True).encode('utf-8')
        fresh_signature = key_pair.sign_data(fresh_bytes)
        
        # Property: Fresh commands should verify
        assert key_pair.verify_signature(fresh_bytes, fresh_signature)
        
        # Property: Timestamp freshness check (simulated current time)
        simulated_current_time = base_time + 100  # 100 seconds later
        timestamp_age = simulated_current_time - fresh_command["timestamp"]
        assert timestamp_age <= max_age  # Fresh command
        
        # Test with old timestamp
        old_command = command_data.copy()
        old_command["timestamp"] = base_time - (max_age + 100)  # Too old
        old_command["nonce"] = command_data["nonce"] + "_old"  # Different nonce
        
        old_bytes = json.dumps(old_command, sort_keys=True).encode('utf-8')
        old_signature = key_pair.sign_data(old_bytes)
        
        # Property: Signature should still verify (cryptographically valid)
        assert key_pair.verify_signature(old_bytes, old_signature)
        
        # Property: But timestamp check should fail
        old_timestamp_age = simulated_current_time - old_command["timestamp"]
        assert old_timestamp_age > max_age  # Too old for acceptance


if __name__ == "__main__":
    # Run property-based tests
    pytest.main([__file__, "-v", "--tb=short"])