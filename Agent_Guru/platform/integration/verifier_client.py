"""
Module: Agent_Guru.platform.integration.verifier_client
Purpose: Verifier System integration client for output validation.

Performance Requirements:
- Time Complexity: O(1) per validation request
- Latency: <100ms per validation (95th percentile)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

import aiohttp

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status of a validation request."""

    VALID = "valid"
    INVALID = "invalid"
    UNCERTAIN = "uncertain"
    ERROR = "error"


@dataclass
class ValidationRequest:
    """Request to validate platform operation output."""

    request_id: UUID = field(default_factory=uuid4)
    operation_id: str = ""
    operation_type: str = ""
    output_data: dict[str, Any] = field(default_factory=dict)
    expected_schema: Optional[dict[str, Any]] = None
    validation_rules: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": str(self.request_id),
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "output_data": self.output_data,
            "expected_schema": self.expected_schema,
            "validation_rules": self.validation_rules,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result of a validation request."""

    request_id: UUID = field(default_factory=uuid4)
    status: ValidationStatus = ValidationStatus.UNCERTAIN
    is_valid: bool = False
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validation_time_ms: float = 0.0
    details: Optional[dict[str, Any]] = None


class VerifierClient:
    """
    Async client for Verifier System integration.

    Provides output validation requests and validation result handling.

    Example:
        >>> client = VerifierClient(base_url="http://localhost:8082")
        >>> await client.connect()
        >>> request = ValidationRequest(operation_id="op-1", output_data={...})
        >>> result = await client.validate_output(request)
        >>> await client.disconnect()
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8082",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {max_retries}")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        self._validations_requested = 0
        self._validations_passed = 0
        self._validations_failed = 0

    async def connect(self) -> None:
        """Establish connection to Verifier System."""
        if self._session is not None:
            raise RuntimeError("Client already connected")
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        logger.info(f"Connected to Verifier System at {self.base_url}")

    async def disconnect(self) -> None:
        """Disconnect from Verifier System."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("Disconnected from Verifier System")

    async def validate_output(
        self, request: ValidationRequest
    ) -> ValidationResult:
        """
        Request output validation from Verifier System.

        Args:
            request: Validation request with output data and rules

        Returns:
            Validation result with status and any violations
        """
        if self._session is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        self._validations_requested += 1
        start = time.monotonic()

        for attempt in range(self.max_retries):
            try:
                url = f"{self.base_url}/api/v1/verify/validate"
                async with self._session.post(
                    url, json=request.to_dict()
                ) as resp:
                    elapsed_ms = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        body = await resp.json()
                        status = ValidationStatus(
                            body.get("status", "uncertain")
                        )
                        result = ValidationResult(
                            request_id=request.request_id,
                            status=status,
                            is_valid=body.get("is_valid", False),
                            violations=body.get("violations", []),
                            warnings=body.get("warnings", []),
                            validation_time_ms=elapsed_ms,
                            details=body.get("details"),
                        )
                        if result.is_valid:
                            self._validations_passed += 1
                        else:
                            self._validations_failed += 1
                        logger.debug(
                            f"Validation {request.operation_id}: {status.value}"
                        )
                        return result
                    logger.warning(f"Verifier returned {resp.status}")
            except Exception as e:
                logger.warning(f"Validation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))

        logger.error(f"Validation failed for operation: {request.operation_id}")
        return ValidationResult(
            request_id=request.request_id,
            status=ValidationStatus.ERROR,
            is_valid=False,
            violations=["Verifier System unavailable"],
        )

    async def validate_batch(
        self, requests: list[ValidationRequest]
    ) -> list[ValidationResult]:
        """
        Validate multiple outputs concurrently.

        Args:
            requests: List of validation requests

        Returns:
            List of validation results in same order
        """
        tasks = [self.validate_output(req) for req in requests]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    def get_statistics(self) -> dict[str, Any]:
        """Get client statistics."""
        return {
            "validations_requested": self._validations_requested,
            "validations_passed": self._validations_passed,
            "validations_failed": self._validations_failed,
            "pass_rate": (
                self._validations_passed / self._validations_requested
                if self._validations_requested > 0
                else 0.0
            ),
        }

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
