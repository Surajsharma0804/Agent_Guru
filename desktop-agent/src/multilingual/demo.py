"""
GURU Multilingual Understanding Demo

Demonstration script showing how to use the GURU multilingual understanding
system with various languages and processing modes.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from .setup import setup_guru_multilingual
from .integration import GuruMultilingualIntegration
from .configuration import SupportedLanguages


class MultilingualDemo:
    """Demonstrates multilingual processing capabilities."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.integration: Optional[GuruMultilingualIntegration] = None
        
    def setup_demo_system(self) -> bool:
        """Setup the multilingual system for demonstration."""
        
        try:
            self.logger.info("Setting up GURU multilingual demo system...")
            
            # Setup with common languages
            success, integration = setup_guru_multilingual(
                enabled_languages=["en", "hi", "ta", "de", "fr"],
                primary_language="en"
            )
            
            if not success:
                self.logger.error("Failed to setup multilingual system")
                return False
                
            self.integration = integration
            self.logger.info("Demo system setup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Demo setup failed: {e}")
            return False
            
    def demonstrate_language_detection(self):
        """Demonstrate language detection capabilities."""
        
        print("\n=== Language Detection Demo ===")
        
        # Mock audio samples for different languages
        test_samples = [
            ("English", b"hello_world_english_audio_mock"),
            ("Hindi", b"namaste_duniya_hindi_audio_mock"),
            ("Tamil", b"vanakkam_ulagam_tamil_audio_mock"),
            ("German", b"hallo_welt_german_audio_mock"),
            ("French", b"bonjour_monde_french_audio_mock")
        ]
        
        for language_name, mock_audio in test_samples:
            print(f"\nTesting {language_name} detection...")
            
            try:
                # In a real demo, this would process actual audio
                # For now, we'll show the expected workflow
                
                result = self.integration.process_voice_input(
                    audio=mock_audio,
                    session_id=f"demo_{language_name.lower()}"
                )
                
                print(f"  Result: {result.get('action', 'FALLBACK')}")
                print(f"  Metadata: {result.get('metadata', {}).get('multilingual_integration', {})}")
                
            except Exception as e:
                print(f"  Error: {e}")
                
    def demonstrate_command_processing(self):
        """Demonstrate multilingual command processing."""
        
        print("\n=== Multilingual Command Processing Demo ===")
        
        # Example commands in different languages
        test_commands = [
            ("English", "open calculator", "OPEN_APPLICATION"),
            ("Hindi", "कैलकुलेटर खोलो", "OPEN_APPLICATION"),
            ("Tamil", "கால்குலேட்டர் ஓபன் பண்ணு", "OPEN_APPLICATION"),
            ("German", "öffne rechner", "OPEN_APPLICATION"),
            ("French", "ouvre calculatrice", "OPEN_APPLICATION")
        ]
        
        for language, command_text, expected_action in test_commands:
            print(f"\nProcessing {language} command: '{command_text}'")
            
            try:
                # Mock audio representing the spoken command
                mock_audio = f"{command_text}_audio_mock".encode('utf-8')
                
                result = self.integration.process_voice_input(
                    audio=mock_audio,
                    session_id=f"command_demo_{language.lower()}"
                )
                
                print(f"  Expected Action: {expected_action}")
                print(f"  Actual Result: {result.get('action', 'FALLBACK')}")
                
                # Show multilingual metadata
                ml_metadata = result.get('metadata', {}).get('multilingual_integration', {})
                if ml_metadata:
                    print(f"  Detected Language: {ml_metadata.get('detected_language', 'unknown')}")
                    print(f"  Processing Mode: {ml_metadata.get('processing_mode', 'unknown')}")
                    print(f"  Processing Time: {ml_metadata.get('processing_time_ms', 0)}ms")
                    
            except Exception as e:
                print(f"  Error: {e}")
                
    def demonstrate_dictation_mode(self):
        """Demonstrate multilingual dictation mode."""
        
        print("\n=== Multilingual Dictation Demo ===")
        
        # Example dictation in different scripts
        dictation_samples = [
            ("English", "Hello, this is a test message in English."),
            ("Hindi", "नमस्ते, यह हिंदी में एक परीक्षण संदेश है।"),
            ("Tamil", "வணக்கம், இது தமிழில் ஒரு சோதனை செய்தி."),
            ("German", "Hallo, das ist eine Testnachricht auf Deutsch."),
            ("French", "Bonjour, ceci est un message de test en français.")
        ]
        
        for language, text in dictation_samples:
            print(f"\nDictating in {language}: '{text}'")
            
            try:
                # Mock audio for dictation
                mock_audio = f"dictation_{text}".encode('utf-8')
                
                result = self.integration.process_voice_input(
                    audio=mock_audio,
                    session_id=f"dictation_demo_{language.lower()}"
                )
                
                print(f"  Action: {result.get('action', 'FALLBACK')}")
                
                # Show parameters for dictation
                parameters = result.get('parameters', {})
                if 'text' in parameters:
                    print(f"  Dictated Text: {parameters['text']}")
                    print(f"  Preserve Exact: {parameters.get('preserve_exact', False)}")
                    
            except Exception as e:
                print(f"  Error: {e}")
                
    def demonstrate_mode_switching(self):
        """Demonstrate mode switching between command and dictation."""
        
        print("\n=== Mode Switching Demo ===")
        
        mode_switch_examples = [
            ("English", "command mode", "Switch to command mode"),
            ("English", "dictation mode", "Switch to dictation mode"),
            ("Hindi", "कमांड मोड", "Switch to command mode"),
            ("Hindi", "डिक्टेशन मोड", "Switch to dictation mode"),
            ("Tamil", "கமாண்ட் மோட்", "Switch to command mode"),
            ("Tamil", "டிக்டேஷன் மோட்", "Switch to dictation mode")
        ]
        
        for language, command, description in mode_switch_examples:
            print(f"\n{description} ({language}): '{command}'")
            
            try:
                mock_audio = f"mode_switch_{command}".encode('utf-8')
                
                result = self.integration.process_voice_input(
                    audio=mock_audio,
                    session_id=f"mode_demo_{language.lower()}"
                )
                
                print(f"  Result: {result.get('action', 'FALLBACK')}")
                
                # Show mode information
                ml_metadata = result.get('metadata', {}).get('multilingual_integration', {})
                if ml_metadata:
                    print(f"  Processing Mode: {ml_metadata.get('processing_mode', 'unknown')}")
                    
            except Exception as e:
                print(f"  Error: {e}")
                
    def demonstrate_security_features(self):
        """Demonstrate security features and validation."""
        
        print("\n=== Security Features Demo ===")
        
        # Examples of commands with different security levels
        security_examples = [
            ("Low Risk", "type hello world", "TYPE_TEXT"),
            ("Medium Risk", "open calculator", "OPEN_APPLICATION"),
            ("High Risk", "delete important file", "DELETE_FILE"),
            ("System Risk", "shutdown computer", "SHUTDOWN_SYSTEM")
        ]
        
        for risk_level, command, action in security_examples:
            print(f"\n{risk_level} Command: '{command}'")
            
            try:
                mock_audio = f"security_test_{command}".encode('utf-8')
                
                result = self.integration.process_voice_input(
                    audio=mock_audio,
                    session_id="security_demo",
                    expected_speaker_id="demo_user"
                )
                
                print(f"  Expected Action: {action}")
                print(f"  Result: {result.get('action', 'FALLBACK')}")
                
                # Show security metadata
                metadata = result.get('metadata', {})
                print(f"  Authority Required: {metadata.get('authority_required', 'unknown')}")
                print(f"  Security Level: {metadata.get('security_level', 'unknown')}")
                
                # Show pipeline metadata
                pipeline_metadata = metadata.get('pipeline_result', {})
                if pipeline_metadata:
                    print(f"  Authority Granted: {pipeline_metadata.get('authority_granted', 'unknown')}")
                    
            except Exception as e:
                print(f"  Error: {e}")
                
    def show_system_statistics(self):
        """Show system statistics and performance metrics."""
        
        print("\n=== System Statistics ===")
        
        try:
            status = self.integration.get_integration_status()
            
            print(f"Integration Active: {status['integration_active']}")
            print(f"Multilingual Enabled: {status['multilingual_enabled']}")
            print(f"Fallback Count: {status['fallback_count']}")
            
            # Show configuration
            config = status.get('configuration', {})
            ml_config = config.get('multilingual_config', {})
            
            print(f"\nEnabled Languages: {ml_config.get('enabled_languages', [])}")
            print(f"Primary Language: {ml_config.get('primary_language', 'unknown')}")
            print(f"Detection Threshold: {ml_config.get('detection_threshold', 0.0)}")
            
            # Show pipeline statistics if available
            pipeline_stats = status.get('pipeline_statistics', {})
            if pipeline_stats:
                print(f"\nPipeline Statistics:")
                print(f"  Total Requests: {pipeline_stats.get('total_requests', 0)}")
                print(f"  Success Rate: {pipeline_stats.get('success_rate', 0.0):.2%}")
                print(f"  Average Processing Time: {pipeline_stats.get('average_processing_time_ms', 0.0):.1f}ms")
                
        except Exception as e:
            print(f"Error getting statistics: {e}")
            
    def run_complete_demo(self):
        """Run the complete demonstration."""
        
        print("GURU Multilingual Understanding System Demo")
        print("=" * 50)
        
        # Setup system
        if not self.setup_demo_system():
            print("Failed to setup demo system")
            return
            
        print(f"\nSupported Languages: {', '.join(SupportedLanguages.get_language_codes())}")
        
        # Run demonstrations
        self.demonstrate_language_detection()
        self.demonstrate_command_processing()
        self.demonstrate_dictation_mode()
        self.demonstrate_mode_switching()
        self.demonstrate_security_features()
        self.show_system_statistics()
        
        print("\n" + "=" * 50)
        print("Demo completed successfully!")
        
        # Cleanup
        if self.integration:
            self.integration.cleanup()


def run_interactive_demo():
    """Run an interactive demo where users can choose what to demonstrate."""
    
    demo = MultilingualDemo()
    
    if not demo.setup_demo_system():
        print("Failed to setup demo system")
        return
        
    while True:
        print("\nGURU Multilingual Demo - Choose an option:")
        print("1. Language Detection")
        print("2. Command Processing")
        print("3. Dictation Mode")
        print("4. Mode Switching")
        print("5. Security Features")
        print("6. System Statistics")
        print("7. Complete Demo")
        print("0. Exit")
        
        try:
            choice = input("\nEnter your choice (0-7): ").strip()
            
            if choice == "0":
                break
            elif choice == "1":
                demo.demonstrate_language_detection()
            elif choice == "2":
                demo.demonstrate_command_processing()
            elif choice == "3":
                demo.demonstrate_dictation_mode()
            elif choice == "4":
                demo.demonstrate_mode_switching()
            elif choice == "5":
                demo.demonstrate_security_features()
            elif choice == "6":
                demo.show_system_statistics()
            elif choice == "7":
                demo.run_complete_demo()
            else:
                print("Invalid choice. Please try again.")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            
    # Cleanup
    if demo.integration:
        demo.integration.cleanup()
        
    print("\nDemo session ended.")


if __name__ == "__main__":
    """Run the demo."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="GURU Multilingual Understanding Demo")
    parser.add_argument("--interactive", action="store_true", help="Run interactive demo")
    parser.add_argument("--complete", action="store_true", help="Run complete demo")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        if args.interactive:
            run_interactive_demo()
        elif args.complete:
            demo = MultilingualDemo()
            demo.run_complete_demo()
        else:
            # Default to interactive
            run_interactive_demo()
            
    except Exception as e:
        print(f"Demo error: {e}")
        logging.getLogger(__name__).error(f"Demo failed: {e}", exc_info=True)