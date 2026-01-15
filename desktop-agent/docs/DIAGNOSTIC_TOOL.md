# GURU System Diagnostic Tool

## Overview

The GURU System Diagnostic Tool is a comprehensive, production-grade diagnostic script that validates all critical system components. It provides detailed pass/fail reporting, actionable error messages, and performance metrics to ensure the GURU system is ready for operation.

## Requirements Validated

This diagnostic tool validates the following requirements:

- **Requirement 19.1**: Test TTS synthesis and audio output
- **Requirement 19.2**: Test voice recognition and wake word detection
- **Requirement 19.3**: Test biometric authentication availability
- **Requirement 19.4**: Test LLM connectivity and response times
- **Requirement 19.5**: Report pass/fail for each test
- **Requirement 19.6**: Provide detailed error messages

## Features

### Comprehensive Component Testing

The diagnostic tool tests all critical GURU components:

1. **Platform Detection**
   - Validates platform detection (Windows, macOS, Android, iOS)
   - Verifies platform information retrieval
   - Ensures correct platform identification

2. **PAL Backend Factory**
   - Tests creation of all 6 PAL interfaces
   - Validates platform-specific backend availability
   - Checks interface initialization

3. **Configuration Integrity**
   - Verifies configuration file existence
   - Validates configuration loading
   - Checks for missing configuration files

4. **TTS Synthesis**
   - Tests text-to-speech synthesis
   - Validates audio output
   - Measures speech synthesis performance
   - Verifies platform-specific TTS backend

5. **Voice Recognition**
   - Tests microphone calibration
   - Validates voice recognition engine availability
   - Checks Whisper.cpp model availability
   - Verifies speech input backend

6. **Biometric Authentication**
   - Tests biometric authentication availability
   - Validates available biometric factors
   - Checks Windows Hello, Touch ID, Face ID support

7. **LLM Connectivity**
   - Tests LLM provider connectivity
   - Validates response times
   - Checks timeout and fallback mechanisms
   - Verifies Ollama service availability

8. **Component Health**
   - Tests health monitoring system
   - Validates component status tracking
   - Checks for failed or degraded components

9. **Audit Logging**
   - Tests audit log write operations
   - Validates signature chain integrity
   - Checks cryptographic verification

### Production-Grade Features

- **Detailed Reporting**: Each test provides pass/fail status with detailed messages
- **Performance Metrics**: Timing information for each test
- **Actionable Remediations**: Specific steps to fix failures
- **Error Handling**: Comprehensive exception handling with detailed error messages
- **Cross-Platform Support**: Works on Windows, macOS, Android, iOS
- **Unicode Support**: Safe printing with fallback for unsupported characters

## Usage

### Windows

Run the diagnostic tool using the provided batch file:

```batch
RUN_DIAGNOSTICS.bat
```

Or run directly with Python:

```batch
python run_diagnostics.py
```

### macOS/Linux

Run directly with Python:

```bash
python3 run_diagnostics.py
```

Or make it executable:

```bash
chmod +x run_diagnostics.py
./run_diagnostics.py
```

## Output Format

### Test Execution

Each test displays:
- Test name
- Status (PASS, FAIL, WARN, SKIP)
- Message describing the result
- Duration in milliseconds
- Additional details
- Remediation steps (if failed)

Example:
```
[TEST] Platform Detection
----------------------------------------------------------------------
  Platform: windows
  System: Windows
  Release: 10
  Architecture: AMD64

✓ PASS: Platform detected: windows
  Duration: 32.00ms
  Details: System: Windows, Release: 10
```

### Summary Report

The summary report includes:
- Total number of tests
- Count of passed, failed, warned, and skipped tests
- Total execution duration
- List of failed tests with remediation steps
- Overall system status

Example:
```
======================================================================
DIAGNOSTIC SUMMARY
======================================================================

Total Tests: 9
  ✓ Passed: 7
  ✗ Failed: 1
  ⚠ Warnings: 1
  ○ Skipped: 0

Total Duration: 5432.12ms

======================================================================
FAILED TESTS
======================================================================

✗ LLM Connectivity
  Message: LLM request timed out
  Details: Timeout after 5000.00ms
  Remediation: Ensure Ollama is running: ollama serve

======================================================================
✗ SOME DIAGNOSTICS FAILED
======================================================================

1 critical issue(s) detected.
Please review failed tests and apply remediations.
```

## Test Status Codes

- **PASS**: Test completed successfully, component is operational
- **FAIL**: Test failed, component is not operational
- **WARN**: Test completed with warnings, component may have limited functionality
- **SKIP**: Test was skipped (not applicable or dependencies missing)

## Exit Codes

- **0**: All diagnostics passed
- **1**: One or more diagnostics failed
- **130**: Diagnostics interrupted by user (Ctrl+C)

## Common Issues and Remediations

### TTS Synthesis Failed

**Symptoms**: TTS synthesis test fails or times out

**Remediation**:
1. Check audio output device is connected and enabled
2. Verify TTS engine is installed (Windows SAPI, NSSpeechSynthesizer, etc.)
3. Check audio permissions in system settings
4. Test audio output with other applications

### Voice Recognition Failed

**Symptoms**: Voice recognition test fails or microphone calibration fails

**Remediation**:
1. Check microphone is connected and enabled
2. Verify microphone permissions in system settings
3. Ensure Whisper.cpp is installed
4. Test microphone with other applications

### Biometric Authentication Not Available

**Symptoms**: Biometric authentication test shows "not available"

**Remediation**:
1. Configure Windows Hello in system settings (Windows)
2. Enable Touch ID or Face ID in system preferences (macOS/iOS)
3. Configure biometric authentication in security settings (Android)
4. Ensure biometric hardware is available and functioning

### LLM Connectivity Failed

**Symptoms**: LLM connectivity test times out or fails

**Remediation**:
1. Ensure Ollama is installed: `ollama --version`
2. Start Ollama service: `ollama serve`
3. Verify models are installed: `ollama list`
4. Check LLM configuration in `llm_config.json`
5. Test Ollama directly: `ollama run qwen2.5:7b-instruct "test"`

### Configuration Files Missing

**Symptoms**: Configuration integrity test shows missing files

**Remediation**:
1. Run setup wizard: `python launch_guru.py`
2. Create configuration manually in `%USERPROFILE%\.guru\`
3. Copy example configuration: `copy llm_config_example.json %USERPROFILE%\.guru\llm_config.json`

## Integration with CI/CD

The diagnostic tool can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run GURU Diagnostics
  run: |
    cd desktop-agent
    python run_diagnostics.py
  continue-on-error: false
```

Exit code 0 indicates all tests passed, non-zero indicates failures.

## Development and Testing

### Running Individual Tests

You can import and run individual tests:

```python
from run_diagnostics import DiagnosticRunner, test_platform_detection

runner = DiagnosticRunner()
result = runner.run_test("Platform Detection", test_platform_detection)
print(f"Status: {result.status.value}")
```

### Adding New Tests

To add a new diagnostic test:

1. Create a test function that returns a `TestResult`:

```python
def test_new_component() -> TestResult:
    """Test new component."""
    try:
        # Test logic here
        return TestResult(
            name="New Component",
            status=TestStatus.PASS,
            message="Component operational",
            details="Additional details"
        )
    except Exception as e:
        return TestResult(
            name="New Component",
            status=TestStatus.FAIL,
            message="Component failed",
            details=str(e),
            remediation="Steps to fix the issue"
        )
```

2. Add the test to the main execution:

```python
def main():
    runner = DiagnosticRunner()
    # ... existing tests ...
    runner.run_test("New Component", test_new_component)
    # ...
```

## Performance Benchmarks

Expected test durations on typical hardware:

- Platform Detection: < 50ms
- PAL Backend Factory: < 200ms
- Configuration Integrity: < 100ms
- TTS Synthesis: 2000-5000ms (includes actual speech)
- Voice Recognition: < 500ms
- Biometric Authentication: < 100ms
- LLM Connectivity: 1000-5000ms (depends on model)
- Component Health: < 100ms
- Audit Logging: < 50ms

Total expected duration: 5-15 seconds

## Security Considerations

The diagnostic tool:
- Does NOT store or transmit sensitive data
- Does NOT perform actual biometric authentication (only checks availability)
- Does NOT modify system configuration
- Does NOT require elevated privileges
- Logs all operations to audit log

## Troubleshooting

### Diagnostic Tool Won't Run

**Issue**: Python import errors or module not found

**Solution**:
1. Ensure you're in the `desktop-agent` directory
2. Verify Python path: `python --version` (should be 3.8+)
3. Install dependencies: `pip install -r requirements.txt`
4. Check PYTHONPATH includes `src` directory

### All Tests Fail

**Issue**: Multiple component failures

**Solution**:
1. Run setup wizard first: `python launch_guru.py`
2. Verify all dependencies installed: `pip install -r requirements.txt`
3. Check system requirements (Windows 10+, Python 3.8+)
4. Review system logs for errors

### Diagnostic Hangs

**Issue**: Diagnostic tool appears to hang or freeze

**Solution**:
1. Press Ctrl+C to interrupt
2. Check for blocking operations (TTS, LLM)
3. Verify network connectivity (for cloud LLM providers)
4. Run with shorter timeout: modify `default_timeout_seconds` in code

## Architecture

### Class Hierarchy

```
DiagnosticRunner
├── run_test() - Execute single test with timing
├── _print_result() - Format and print test result
└── print_summary() - Print comprehensive summary

TestResult (dataclass)
├── name: str
├── status: TestStatus
├── message: str
├── details: Optional[str]
├── duration_ms: Optional[float]
└── remediation: Optional[str]

TestStatus (enum)
├── PASS
├── FAIL
├── WARN
└── SKIP
```

### Test Functions

Each test function:
1. Imports required modules
2. Performs component-specific tests
3. Returns `TestResult` with status and details
4. Handles exceptions gracefully
5. Provides actionable remediation steps

## Future Enhancements

Planned improvements:
- [ ] Parallel test execution for faster completion
- [ ] JSON output format for machine parsing
- [ ] Detailed performance profiling
- [ ] Network connectivity tests
- [ ] Database integrity checks
- [ ] Memory leak detection
- [ ] Resource usage monitoring
- [ ] Automated remediation for common issues

## References

- **Requirements Document**: `.kiro/specs/guru-complete-system/requirements.md`
- **Design Document**: `.kiro/specs/guru-complete-system/design.md`
- **Task List**: `.kiro/specs/guru-complete-system/tasks.md`
- **Platform Abstraction Layer**: `src/pal/`
- **Component Health Monitoring**: `src/failure/`
- **Audit Logging**: `src/audit/`

## Support

For issues or questions:
1. Review this documentation
2. Check remediation steps for failed tests
3. Review system logs in `logs/`
4. Review audit logs in `audit_logs/`
5. Consult the main GURU documentation

---

**Version**: 1.0.0  
**Last Updated**: 2026-01-15  
**Requirements**: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6
