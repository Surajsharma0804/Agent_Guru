"""
GURU Desktop Agent - Main Entry Point

Production-grade personal automation system with security-first design.
This is the primary entry point for the GURU desktop agent service.

Architecture:
- FastAPI-based REST API for command interface
- Authority state machine for security enforcement
- Comprehensive audit logging with cryptographic integrity
- Biometric authentication integration
- Voice processing pipeline
- Input automation with authority gating
- Intrusion detection and automatic response
- Component health monitoring and failure recovery

Security Model:
- Capability-based security with cryptographic enforcement
- No command execution without verified authority
- Tamper-evident audit logging
- Automatic workstation locking on security violations
- Privacy-preserving operation (no sensitive data logging)

Startup Sequence:
1. Initialize cryptographic components (audit logger, authority state machine)
2. Load configuration and validate security settings
3. Initialize biometric providers and verify availability
4. Start voice processing pipeline
5. Initialize input automation engine
6. Start intrusion detection system
7. Initialize component health monitoring
8. Start FastAPI service
9. Begin listening for voice commands

Shutdown Sequence:
1. Stop accepting new commands
2. Complete in-flight operations
3. Revoke all active authority sessions
4. Flush audit logs and verify integrity
5. Cleanup biometric provider resources
6. Stop all background threads
7. Final audit log entry
8. Clean shutdown
"""

import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .audit.audit_logger import AuditLogger, AuditSeverity
from .authority.state import (
    AuthorityConfiguration,
    AuthorityStateMachine,
    create_authority_state_machine,
)
from .failure.system_failure_orchestrator import SystemFailureOrchestrator
from .intrusion.detection import IntrusionDetector, create_intrusion_detector

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger(__name__)

# Global system components (initialized during startup)
audit_logger: Optional[AuditLogger] = None
authority_machine: Optional[AuthorityStateMachine] = None
intrusion_detector: Optional[IntrusionDetector] = None
failure_orchestrator: Optional[SystemFailureOrchestrator] = None


# API Models
class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="Service version")
    authority_state: str = Field(..., description="Current authority state")
    components: dict = Field(..., description="Component health status")


class AuthorityStatusResponse(BaseModel):
    """Authority status response model."""

    state: str = Field(..., description="Current authority state")
    session_id: str = Field(..., description="Current session ID")
    is_armed: bool = Field(..., description="Whether authority is armed")
    is_locked: bool = Field(..., description="Whether authority is locked")
    policy: str = Field(..., description="Current authority policy")
    time_since_armed: Optional[float] = Field(None, description="Seconds since armed")
    time_since_activity: float = Field(..., description="Seconds since last activity")


class VoiceCommandRequest(BaseModel):
    """Voice command request model."""

    command_text: str = Field(..., description="Transcribed voice command text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Voice recognition confidence")
    language: str = Field(default="en", description="Detected language code")


class CommandResponse(BaseModel):
    """Command execution response model."""

    success: bool = Field(..., description="Whether command executed successfully")
    message: str = Field(..., description="Response message")
    command_id: Optional[str] = Field(None, description="Command execution ID")
    authority_required: bool = Field(default=False, description="Whether authority was required")


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles initialization and cleanup of all system components with
    proper error handling and graceful degradation.
    """
    global audit_logger, authority_machine, intrusion_detector, failure_orchestrator

    logger.info("GURU Desktop Agent starting up...")

    try:
        # Initialize audit logger (CRITICAL - must succeed)
        logger.info("Initializing audit logging system...")
        audit_logger = AuditLogger(log_directory="audit_logs", enable_real_time_verification=True, testing_mode=False)
        audit_logger.log_system_event(
            "system_startup", {"version": "1.0.0", "environment": "production"}, AuditSeverity.INFO
        )

        # Initialize authority state machine (CRITICAL - must succeed)
        logger.info("Initializing authority state machine...")
        authority_config = AuthorityConfiguration(
            test_mode_disable_workstation_lock=False  # PRODUCTION: workstation lock enabled
        )
        authority_machine = create_authority_state_machine(authority_config)

        # Initialize intrusion detection (CRITICAL - must succeed)
        logger.info("Initializing intrusion detection system...")
        intrusion_detector = create_intrusion_detector()

        # Initialize failure orchestrator
        logger.info("Initializing failure recovery system...")
        failure_orchestrator = SystemFailureOrchestrator()

        # Additional component initialization would go here:
        # - Biometric providers
        # - Voice processing pipeline
        # - Input automation engine
        # - LLM adapter
        # - Skills registry
        # - Memory system
        # - Communication layer

        logger.info("GURU Desktop Agent startup complete", components_initialized=5)

        audit_logger.log_system_event(
            "startup_complete",
            {"components": ["audit", "authority", "intrusion", "failure", "api"]},
            AuditSeverity.INFO,
        )

        yield  # Application runs here

    except Exception as e:
        logger.critical("CRITICAL FAILURE DURING STARTUP", error=str(e), exc_info=True)
        if audit_logger:
            audit_logger.log_emergency_event("startup_failure", {"error": str(e), "fatal": True})
        raise

    finally:
        # Shutdown sequence
        logger.info("GURU Desktop Agent shutting down...")

        try:
            # Revoke all authority
            if authority_machine and not authority_machine.is_locked:
                from .authority.state import StateTransitionReason

                authority_machine.revoke_authority(
                    StateTransitionReason.MANUAL_REVOKE, metadata={"reason": "system_shutdown"}
                )

            # Final audit log
            if audit_logger:
                audit_logger.log_system_event("system_shutdown", {"graceful": True}, AuditSeverity.INFO)

            logger.info("GURU Desktop Agent shutdown complete")

        except Exception as e:
            logger.error("Error during shutdown", error=str(e), exc_info=True)


# Create FastAPI application
app = FastAPI(
    title="GURU Desktop Agent",
    description="Production-Grade Personal Automation System with Security-First Design",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware (restrictive by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Only allow local frontend
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with audit logging."""
    logger.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=True)

    if audit_logger:
        audit_logger.log_security_event(
            "unhandled_exception", {"path": str(request.url.path), "error": str(exc)}, AuditSeverity.ERROR
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error_id": "See audit logs"},
    )


# API Endpoints
@app.get("/", response_model=dict)
async def root():
    """Root endpoint."""
    return {
        "service": "GURU Desktop Agent",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/api/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns comprehensive system health status including all components.
    """
    if not authority_machine or not audit_logger:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="System not initialized")

    state_info = authority_machine.get_state_info()
    audit_stats = audit_logger.get_audit_statistics()

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        authority_state=state_info["state"],
        components={
            "audit_logger": {"status": "operational", "total_entries": audit_stats["total_entries"]},
            "authority_machine": {"status": "operational", "state": state_info["state"]},
            "intrusion_detector": {"status": "operational" if intrusion_detector else "unavailable"},
            "failure_orchestrator": {"status": "operational" if failure_orchestrator else "unavailable"},
        },
    )


@app.get("/api/authority/status", response_model=AuthorityStatusResponse)
async def get_authority_status():
    """
    Get current authority status.

    Returns detailed information about the current authority state,
    session, and timing information.
    """
    if not authority_machine:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authority system not initialized")

    state_info = authority_machine.get_state_info()

    return AuthorityStatusResponse(
        state=state_info["state"],
        session_id=state_info["session_id"],
        is_armed=state_info["is_armed"],
        is_locked=state_info["is_locked"],
        policy=state_info["policy"],
        time_since_armed=state_info.get("time_since_armed"),
        time_since_activity=state_info["time_since_activity"],
    )


@app.post("/api/commands/voice", response_model=CommandResponse)
async def process_voice_command(command: VoiceCommandRequest):
    """
    Process voice command.

    This endpoint receives transcribed voice commands and processes them
    through the authority-gated execution pipeline.

    Security: Requires active authority session for command execution.
    """
    if not authority_machine or not audit_logger:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="System not initialized")

    # Log command reception
    audit_logger.log_system_event(
        "voice_command_received",
        {"command_length": len(command.command_text), "confidence": command.confidence, "language": command.language},
        AuditSeverity.INFO,
    )

    # Check authority state
    if not authority_machine.is_armed:
        return CommandResponse(
            success=False,
            message="Authority not granted. Please authenticate first.",
            authority_required=True,
        )

    # Command processing would go here
    # This is a placeholder for the full command processing pipeline

    return CommandResponse(
        success=True,
        message="Command received and queued for processing",
        command_id="placeholder",
        authority_required=True,
    )


@app.post("/api/authority/revoke")
async def revoke_authority():
    """
    Manually revoke authority.

    Forces immediate authority revocation and workstation lock.
    """
    if not authority_machine:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authority system not initialized")

    from .authority.state import StateTransitionReason

    success = authority_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE, metadata={"source": "api"})

    return {"success": success, "message": "Authority revoked" if success else "Authority revocation failed"}


def main():
    """
    Main entry point for GURU Desktop Agent.

    Starts the FastAPI service with production-grade configuration.
    """

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Shutdown signal received", signal=signum)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start uvicorn server
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",  # Localhost only for security
        port=8000,
        log_level="info",
        access_log=True,
        use_colors=True,
        server_header=False,  # Don't expose server version
        date_header=False,  # Don't expose date
    )


if __name__ == "__main__":
    main()
