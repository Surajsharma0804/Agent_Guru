"""
Data Residency and Regional Compliance

Production-grade data residency controls and regional compliance implementation
for multilingual processing. Ensures language-specific data stays within
appropriate jurisdictions and complies with regional regulations.

This module implements Task 13.2 requirements:
- Create language-specific data residency controls
- Implement regional compliance requirements for different languages
- Maintain existing security documentation standards

Requirements: 16.4, 16.5
"""

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audit_logging import AuditSeverity, MultilingualAuditContext, MultilingualAuditLogger, MultilingualEventType
from .configuration import MultilingualConfig


class DataResidencyRegion(Enum):
    """Supported data residency regions."""
    
    # European Union
    EU = "eu"
    EEA = "eea"
    
    # North America
    US = "us"
    CA = "ca"
    MX = "mx"
    
    # Asia Pacific
    IN = "in"
    CN = "cn"
    JP = "jp"
    SG = "sg"
    AU = "au"
    
    # Other regions
    UK = "uk"
    BR = "br"
    ZA = "za"


class DataCategory(Enum):
    """Categories of data subject to residency requirements."""
    
    VOICE_DATA = "voice_data"
    LANGUAGE_MODELS = "language_models"
    USER_PREFERENCES = "user_preferences"
    PROCESSING_LOGS = "processing_logs"
    AUDIT_LOGS = "audit_logs"
    TRAINING_DATA = "training_data"
    CACHE_DATA = "cache_data"


@dataclass
class ResidencyRequirement:
    """Data residency requirement configuration."""
    
    requirement_id: str
    region: DataResidencyRegion
    data_categories: List[DataCategory]
    languages: List[str]
    storage_location: str  # Physical storage location
    encryption_required: bool = True
    cross_border_transfer_allowed: bool = False
    approved_transfer_regions: List[DataResidencyRegion] = field(default_factory=list)
    regulatory_basis: str = ""  # Legal basis for requirement
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'requirement_id': self.requirement_id,
            'region': self.region.value,
            'data_categories': [cat.value for cat in self.data_categories],
            'languages': self.languages,
            'storage_location': self.storage_location,
            'encryption_required': self.encryption_required,
            'cross_border_transfer_allowed': self.cross_border_transfer_allowed,
            'approved_transfer_regions': [r.value for r in self.approved_transfer_regions],
            'regulatory_basis': self.regulatory_basis,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


@dataclass
class DataTransferRequest:
    """Request for cross-border data transfer."""
    
    request_id: str
    source_region: DataResidencyRegion
    destination_region: DataResidencyRegion
    data_category: DataCategory
    language: str
    justification: str
    requested_at: datetime
    approved: bool = False
    approval_timestamp: Optional[datetime] = None
    approver: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'request_id': self.request_id,
            'source_region': self.source_region.value,
            'destination_region': self.destination_region.value,
            'data_category': self.data_category.value,
            'language': self.language,
            'justification': self.justification,
            'requested_at': self.requested_at.isoformat(),
            'approved': self.approved,
            'approval_timestamp': self.approval_timestamp.isoformat() if self.approval_timestamp else None,
            'approver': self.approver
        }


@dataclass
class RegionalComplianceRule:
    """Regional compliance rule configuration."""
    
    rule_id: str
    region: DataResidencyRegion
    languages: List[str]
    rule_type: str  # 'data_localization', 'consent_requirement', 'retention_limit', etc.
    description: str
    enforcement_level: str = "mandatory"  # 'mandatory', 'recommended', 'optional'
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'rule_id': self.rule_id,
            'region': self.region.value,
            'languages': self.languages,
            'rule_type': self.rule_type,
            'description': self.description,
            'enforcement_level': self.enforcement_level,
            'parameters': self.parameters,
            'created_at': self.created_at.isoformat()
        }


class DataResidencyController:
    """
    Direct control of data residency and regional compliance for multilingual processing.
    
    Controls data storage location, processing boundaries, and compliance
    with regional data protection regulations (GDPR, CCPA, etc.).
    
    This controller manages:
    - Data residency policy enforcement
    - Regional compliance validation
    - Cross-border data transfer restrictions
    - Data localization requirements
    - Compliance audit logging
    - Regional configuration management
    
    This class implements language-specific data residency controls and ensures
    compliance with regional data protection regulations. It provides:
    
    - Language-specific data residency enforcement
    - Regional compliance rule management
    - Cross-border data transfer controls
    - Audit trail for all data movements
    - Integration with existing GURU security infrastructure
    
    Requirements: 16.4, 16.5
    """
    
    def __init__(self,
                 config: MultilingualConfig,
                 audit_logger: MultilingualAuditLogger,
                 residency_data_path: Optional[Path] = None):
        """
        Initialize data residency manager.
        
        Args:
            config: Multilingual configuration
            audit_logger: Multilingual audit logger
            residency_data_path: Path for residency data storage
        """
        self.config = config
        self.audit_logger = audit_logger
        self.logger = logging.getLogger(__name__)
        
        # Residency data storage
        self.residency_data_path = residency_data_path or Path("residency_data")
        self.residency_data_path.mkdir(parents=True, exist_ok=True)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Residency requirements
        self._requirements: Dict[str, ResidencyRequirement] = {}
        self._load_requirements()
        
        # Regional compliance rules
        self._compliance_rules: Dict[str, RegionalComplianceRule] = {}
        self._load_compliance_rules()
        
        # Transfer requests
        self._transfer_requests: Dict[str, DataTransferRequest] = {}
        self._load_transfer_requests()
        
        # Language-to-region mapping
        self._language_region_map = self._build_language_region_map()
        
        # Statistics
        self._residency_stats = {
            'total_requirements': 0,
            'total_compliance_rules': 0,
            'transfer_requests_total': 0,
            'transfer_requests_approved': 0,
            'transfer_requests_denied': 0,
            'residency_violations_detected': 0,
            'last_compliance_check': None
        }
        
        # Initialize default requirements
        self._initialize_default_requirements()
        
        # Log initialization
        self._log_initialization()
    
    def _build_language_region_map(self) -> Dict[str, DataResidencyRegion]:
        """Build mapping of languages to their primary regions."""
        return {
            # European languages
            'en': DataResidencyRegion.EU,  # Default to EU for GDPR compliance
            'de': DataResidencyRegion.EU,
            'fr': DataResidencyRegion.EU,
            
            # Asian languages
            'zh': DataResidencyRegion.CN,
            'ja': DataResidencyRegion.JP,
            
            # Indian languages
            'hi': DataResidencyRegion.IN,
            'ta': DataResidencyRegion.IN,
            'te': DataResidencyRegion.IN,
            'bn': DataResidencyRegion.IN,
            'mr': DataResidencyRegion.IN,
            'gu': DataResidencyRegion.IN,
            'kn': DataResidencyRegion.IN,
            'ml': DataResidencyRegion.IN,
            'pa': DataResidencyRegion.IN,
            'bho': DataResidencyRegion.IN
        }
    
    def _initialize_default_requirements(self):
        """Initialize default data residency requirements."""
        
        # EU data residency for European languages
        eu_requirement = ResidencyRequirement(
            requirement_id="eu_gdpr_residency",
            region=DataResidencyRegion.EU,
            data_categories=[
                DataCategory.VOICE_DATA,
                DataCategory.USER_PREFERENCES,
                DataCategory.PROCESSING_LOGS
            ],
            languages=['en', 'de', 'fr'],
            storage_location="eu-central",
            encryption_required=True,
            cross_border_transfer_allowed=False,
            regulatory_basis="GDPR Article 44-50"
        )
        
        # India data residency for Indian languages
        in_requirement = ResidencyRequirement(
            requirement_id="in_it_act_residency",
            region=DataResidencyRegion.IN,
            data_categories=[
                DataCategory.VOICE_DATA,
                DataCategory.USER_PREFERENCES,
                DataCategory.PROCESSING_LOGS,
                DataCategory.AUDIT_LOGS
            ],
            languages=['hi', 'ta', 'te', 'bn', 'mr', 'gu', 'kn', 'ml', 'pa', 'bho'],
            storage_location="in-mumbai",
            encryption_required=True,
            cross_border_transfer_allowed=False,
            regulatory_basis="IT Act 2000, Personal Data Protection Bill"
        )
        
        # China data residency
        cn_requirement = ResidencyRequirement(
            requirement_id="cn_cybersecurity_residency",
            region=DataResidencyRegion.CN,
            data_categories=[
                DataCategory.VOICE_DATA,
                DataCategory.LANGUAGE_MODELS,
                DataCategory.USER_PREFERENCES,
                DataCategory.PROCESSING_LOGS,
                DataCategory.AUDIT_LOGS
            ],
            languages=['zh'],
            storage_location="cn-beijing",
            encryption_required=True,
            cross_border_transfer_allowed=False,
            regulatory_basis="Cybersecurity Law of China"
        )
        
        # Register default requirements
        for requirement in [eu_requirement, in_requirement, cn_requirement]:
            if requirement.requirement_id not in self._requirements:
                self.register_requirement(requirement)
        
        # Initialize default compliance rules
        self._initialize_default_compliance_rules()
    
    def _initialize_default_compliance_rules(self):
        """Initialize default regional compliance rules."""
        
        # EU GDPR rules
        eu_consent_rule = RegionalComplianceRule(
            rule_id="eu_explicit_consent",
            region=DataResidencyRegion.EU,
            languages=['en', 'de', 'fr'],
            rule_type="consent_requirement",
            description="Explicit user consent required for voice data processing",
            enforcement_level="mandatory",
            parameters={'consent_type': 'explicit', 'withdrawal_allowed': True}
        )
        
        # India IT Act rules
        in_localization_rule = RegionalComplianceRule(
            rule_id="in_data_localization",
            region=DataResidencyRegion.IN,
            languages=['hi', 'ta', 'te', 'bn', 'mr', 'gu', 'kn', 'ml', 'pa', 'bho'],
            rule_type="data_localization",
            description="Critical personal data must be stored within India",
            enforcement_level="mandatory",
            parameters={'allow_mirroring': True, 'require_local_copy': True}
        )
        
        # China Cybersecurity Law rules
        cn_localization_rule = RegionalComplianceRule(
            rule_id="cn_strict_localization",
            region=DataResidencyRegion.CN,
            languages=['zh'],
            rule_type="data_localization",
            description="All personal information and important data must be stored in China",
            enforcement_level="mandatory",
            parameters={'cross_border_transfer': 'prohibited', 'security_assessment_required': True}
        )
        
        # Register default rules
        for rule in [eu_consent_rule, in_localization_rule, cn_localization_rule]:
            if rule.rule_id not in self._compliance_rules:
                self.register_compliance_rule(rule)
    
    def _load_requirements(self):
        """Load residency requirements from storage."""
        requirements_file = self.residency_data_path / "requirements.json"
        
        if requirements_file.exists():
            try:
                with open(requirements_file, 'r') as f:
                    requirements_data = json.load(f)
                    
                for req_data in requirements_data:
                    requirement = ResidencyRequirement(
                        requirement_id=req_data['requirement_id'],
                        region=DataResidencyRegion(req_data['region']),
                        data_categories=[DataCategory(cat) for cat in req_data['data_categories']],
                        languages=req_data['languages'],
                        storage_location=req_data['storage_location'],
                        encryption_required=req_data.get('encryption_required', True),
                        cross_border_transfer_allowed=req_data.get('cross_border_transfer_allowed', False),
                        approved_transfer_regions=[DataResidencyRegion(r) for r in req_data.get('approved_transfer_regions', [])],
                        regulatory_basis=req_data.get('regulatory_basis', ''),
                        created_at=datetime.fromisoformat(req_data['created_at']),
                        updated_at=datetime.fromisoformat(req_data['updated_at'])
                    )
                    self._requirements[requirement.requirement_id] = requirement
                    
                self.logger.info(f"Loaded {len(self._requirements)} residency requirements")
                
            except Exception as e:
                self.logger.error(f"Failed to load residency requirements: {e}")
    
    def _save_requirements(self):
        """Save residency requirements to storage."""
        requirements_file = self.residency_data_path / "requirements.json"
        
        try:
            requirements_data = [req.to_dict() for req in self._requirements.values()]
            
            with open(requirements_file, 'w') as f:
                json.dump(requirements_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save residency requirements: {e}")
    
    def _load_compliance_rules(self):
        """Load regional compliance rules from storage."""
        rules_file = self.residency_data_path / "compliance_rules.json"
        
        if rules_file.exists():
            try:
                with open(rules_file, 'r') as f:
                    rules_data = json.load(f)
                    
                for rule_data in rules_data:
                    rule = RegionalComplianceRule(
                        rule_id=rule_data['rule_id'],
                        region=DataResidencyRegion(rule_data['region']),
                        languages=rule_data['languages'],
                        rule_type=rule_data['rule_type'],
                        description=rule_data['description'],
                        enforcement_level=rule_data.get('enforcement_level', 'mandatory'),
                        parameters=rule_data.get('parameters', {}),
                        created_at=datetime.fromisoformat(rule_data['created_at'])
                    )
                    self._compliance_rules[rule.rule_id] = rule
                    
                self.logger.info(f"Loaded {len(self._compliance_rules)} compliance rules")
                
            except Exception as e:
                self.logger.error(f"Failed to load compliance rules: {e}")
    
    def _save_compliance_rules(self):
        """Save regional compliance rules to storage."""
        rules_file = self.residency_data_path / "compliance_rules.json"
        
        try:
            rules_data = [rule.to_dict() for rule in self._compliance_rules.values()]
            
            with open(rules_file, 'w') as f:
                json.dump(rules_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save compliance rules: {e}")
    
    def _load_transfer_requests(self):
        """Load data transfer requests from storage."""
        requests_file = self.residency_data_path / "transfer_requests.json"
        
        if requests_file.exists():
            try:
                with open(requests_file, 'r') as f:
                    requests_data = json.load(f)
                    
                for req_data in requests_data:
                    request = DataTransferRequest(
                        request_id=req_data['request_id'],
                        source_region=DataResidencyRegion(req_data['source_region']),
                        destination_region=DataResidencyRegion(req_data['destination_region']),
                        data_category=DataCategory(req_data['data_category']),
                        language=req_data['language'],
                        justification=req_data['justification'],
                        requested_at=datetime.fromisoformat(req_data['requested_at']),
                        approved=req_data.get('approved', False),
                        approval_timestamp=datetime.fromisoformat(req_data['approval_timestamp']) if req_data.get('approval_timestamp') else None,
                        approver=req_data.get('approver')
                    )
                    self._transfer_requests[request.request_id] = request
                    
                self.logger.info(f"Loaded {len(self._transfer_requests)} transfer requests")
                
            except Exception as e:
                self.logger.error(f"Failed to load transfer requests: {e}")
    
    def _save_transfer_requests(self):
        """Save data transfer requests to storage."""
        requests_file = self.residency_data_path / "transfer_requests.json"
        
        try:
            requests_data = [req.to_dict() for req in self._transfer_requests.values()]
            
            with open(requests_file, 'w') as f:
                json.dump(requests_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save transfer requests: {e}")
    
    def _log_initialization(self):
        """Log data residency manager initialization."""
        self.audit_logger.log_multilingual_event(
            event_type=MultilingualEventType.MULTILINGUAL_CONFIGURATION_LOADED,
            action='data_residency_manager_initialized',
            multilingual_context=MultilingualAuditContext(),
            severity=AuditSeverity.INFO,
            additional_details={
                'component': 'data_residency_manager',
                'total_requirements': len(self._requirements),
                'total_compliance_rules': len(self._compliance_rules),
                'supported_regions': [r.value for r in DataResidencyRegion],
                'residency_data_path': str(self.residency_data_path)
            }
        )

    def register_requirement(self, requirement: ResidencyRequirement) -> bool:
        """
        Register a new data residency requirement.
        
        Args:
            requirement: Residency requirement to register
            
        Returns:
            True if registered successfully, False otherwise
        """
        with self._lock:
            try:
                self._requirements[requirement.requirement_id] = requirement
                self._save_requirements()
                
                self._residency_stats['total_requirements'] = len(self._requirements)
                
                self.audit_logger.log_multilingual_event(
                    event_type=MultilingualEventType.MULTILINGUAL_CONFIGURATION_UPDATED,
                    action='register_residency_requirement',
                    multilingual_context=MultilingualAuditContext(),
                    severity=AuditSeverity.INFO,
                    additional_details={
                        'requirement_id': requirement.requirement_id,
                        'region': requirement.region.value,
                        'languages': requirement.languages,
                        'data_categories': [cat.value for cat in requirement.data_categories]
                    }
                )
                
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to register residency requirement: {e}")
                return False
    
    def register_compliance_rule(self, rule: RegionalComplianceRule) -> bool:
        """
        Register a new regional compliance rule.
        
        Args:
            rule: Compliance rule to register
            
        Returns:
            True if registered successfully, False otherwise
        """
        with self._lock:
            try:
                self._compliance_rules[rule.rule_id] = rule
                self._save_compliance_rules()
                
                self._residency_stats['total_compliance_rules'] = len(self._compliance_rules)
                
                self.audit_logger.log_multilingual_event(
                    event_type=MultilingualEventType.MULTILINGUAL_CONFIGURATION_UPDATED,
                    action='register_compliance_rule',
                    multilingual_context=MultilingualAuditContext(),
                    severity=AuditSeverity.INFO,
                    additional_details={
                        'rule_id': rule.rule_id,
                        'region': rule.region.value,
                        'rule_type': rule.rule_type,
                        'enforcement_level': rule.enforcement_level
                    }
                )
                
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to register compliance rule: {e}")
                return False
    
    def get_residency_region(self, language: str) -> Optional[DataResidencyRegion]:
        """
        Get the data residency region for a language.
        
        Args:
            language: Language code
            
        Returns:
            Data residency region for the language, or None if not mapped
        """
        return self._language_region_map.get(language)
    
    def check_residency_compliance(self,
                                   language: str,
                                   data_category: DataCategory,
                                   storage_location: str) -> Dict[str, Any]:
        """
        Check if data storage complies with residency requirements.
        
        Args:
            language: Language code
            data_category: Category of data being stored
            storage_location: Proposed storage location
            
        Returns:
            Compliance check result
        """
        with self._lock:
            try:
                self._residency_stats['last_compliance_check'] = datetime.now(timezone.utc).isoformat()
                
                # Get applicable requirements
                applicable_requirements = [
                    req for req in self._requirements.values()
                    if language in req.languages and data_category in req.data_categories
                ]
                
                if not applicable_requirements:
                    # No specific requirements for this language/category
                    return {
                        'compliant': True,
                        'language': language,
                        'data_category': data_category.value,
                        'storage_location': storage_location,
                        'requirements_checked': 0,
                        'message': 'No specific residency requirements'
                    }
                
                violations = []
                
                for requirement in applicable_requirements:
                    # Check if storage location matches required region
                    if not self._is_location_in_region(storage_location, requirement.region):
                        violations.append({
                            'requirement_id': requirement.requirement_id,
                            'region': requirement.region.value,
                            'violation': f"Storage location {storage_location} not in required region {requirement.region.value}",
                            'regulatory_basis': requirement.regulatory_basis
                        })
                
                compliant = len(violations) == 0
                
                if not compliant:
                    self._residency_stats['residency_violations_detected'] += 1
                
                # Log compliance check
                self.audit_logger.log_multilingual_event(
                    event_type=MultilingualEventType.MULTILINGUAL_CONFIGURATION_LOADED,
                    action='residency_compliance_check',
                    multilingual_context=MultilingualAuditContext(
                        original_language=language
                    ),
                    severity=AuditSeverity.WARNING if not compliant else AuditSeverity.INFO,
                    additional_details={
                        'language': language,
                        'data_category': data_category.value,
                        'storage_location': storage_location,
                        'compliant': compliant,
                        'requirements_checked': len(applicable_requirements),
                        'violations_detected': len(violations)
                    }
                )
                
                return {
                    'compliant': compliant,
                    'language': language,
                    'data_category': data_category.value,
                    'storage_location': storage_location,
                    'requirements_checked': len(applicable_requirements),
                    'violations': violations,
                    'checked_at': datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                self.logger.error(f"Residency compliance check failed: {e}")
                return {
                    'compliant': False,
                    'error': str(e),
                    'checked_at': datetime.now(timezone.utc).isoformat()
                }
    
    def _is_location_in_region(self, location: str, region: DataResidencyRegion) -> bool:
        """
        Check if a storage location is within a data residency region.
        
        Args:
            location: Storage location identifier
            region: Data residency region
            
        Returns:
            True if location is in region, False otherwise
        """
        # Simple prefix matching - in production, this would use a comprehensive mapping
        region_prefixes = {
            DataResidencyRegion.EU: ['eu-', 'europe-'],
            DataResidencyRegion.EEA: ['eu-', 'europe-', 'eea-'],
            DataResidencyRegion.US: ['us-', 'usa-'],
            DataResidencyRegion.CA: ['ca-', 'canada-'],
            DataResidencyRegion.IN: ['in-', 'india-'],
            DataResidencyRegion.CN: ['cn-', 'china-'],
            DataResidencyRegion.JP: ['jp-', 'japan-'],
            DataResidencyRegion.SG: ['sg-', 'singapore-'],
            DataResidencyRegion.AU: ['au-', 'australia-'],
            DataResidencyRegion.UK: ['uk-', 'britain-'],
            DataResidencyRegion.BR: ['br-', 'brazil-'],
            DataResidencyRegion.ZA: ['za-', 'south-africa-']
        }
        
        prefixes = region_prefixes.get(region, [])
        return any(location.lower().startswith(prefix) for prefix in prefixes)
    
    def request_data_transfer(self,
                             source_region: DataResidencyRegion,
                             destination_region: DataResidencyRegion,
                             data_category: DataCategory,
                             language: str,
                             justification: str) -> str:
        """
        Request approval for cross-border data transfer.
        
        Args:
            source_region: Source data region
            destination_region: Destination data region
            data_category: Category of data to transfer
            language: Language of the data
            justification: Justification for the transfer
            
        Returns:
            Transfer request ID
        """
        with self._lock:
            try:
                request_id = str(uuid.uuid4())
                
                request = DataTransferRequest(
                    request_id=request_id,
                    source_region=source_region,
                    destination_region=destination_region,
                    data_category=data_category,
                    language=language,
                    justification=justification,
                    requested_at=datetime.now(timezone.utc)
                )
                
                self._transfer_requests[request_id] = request
                self._save_transfer_requests()
                
                self._residency_stats['transfer_requests_total'] += 1
                
                # Log transfer request
                self.audit_logger.log_multilingual_event(
                    event_type=MultilingualEventType.MULTILINGUAL_CONFIGURATION_UPDATED,
                    action='request_data_transfer',
                    multilingual_context=MultilingualAuditContext(
                        original_language=language
                    ),
                    severity=AuditSeverity.WARNING,
                    additional_details={
                        'request_id': request_id,
                        'source_region': source_region.value,
                        'destination_region': destination_region.value,
                        'data_category': data_category.value,
                        'language': language,
                        'justification': justification
                    }
                )
                
                return request_id
                
            except Exception as e:
                self.logger.error(f"Failed to create transfer request: {e}")
                raise
    
    def approve_transfer_request(self, request_id: str, approver: str) -> bool:
        """
        Approve a data transfer request.
        
        Args:
            request_id: Transfer request ID
            approver: Identifier of the approver
            
        Returns:
            True if approved successfully, False otherwise
        """
        with self._lock:
            if request_id not in self._transfer_requests:
                return False
                
            try:
                request = self._transfer_requests[request_id]
                request.approved = True
                request.approval_timestamp = datetime.now(timezone.utc)
                request.approver = approver
                
                self._save_transfer_requests()
                
                self._residency_stats['transfer_requests_approved'] += 1
                
                # Log approval
                self.audit_logger.log_multilingual_event(
                    event_type=MultilingualEventType.MULTILINGUAL_CONFIGURATION_UPDATED,
                    action='approve_data_transfer',
                    multilingual_context=MultilingualAuditContext(),
                    severity=AuditSeverity.INFO,
                    additional_details={
                        'request_id': request_id,
                        'source_region': request.source_region.value,
                        'destination_region': request.destination_region.value,
                        'approver': approver
                    }
                )
                
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to approve transfer request: {e}")
                return False
    
    def deny_transfer_request(self, request_id: str, reason: str) -> bool:
        """
        Deny a data transfer request.
        
        Args:
            request_id: Transfer request ID
            reason: Reason for denial
            
        Returns:
            True if denied successfully, False otherwise
        """
        with self._lock:
            if request_id not in self._transfer_requests:
                return False
                
            try:
                # Remove the request
                request = self._transfer_requests[request_id]
                del self._transfer_requests[request_id]
                self._save_transfer_requests()
                
                self._residency_stats['transfer_requests_denied'] += 1
                
                # Log denial
                self.audit_logger.log_multilingual_event(
                    event_type=MultilingualEventType.SECURITY_VIOLATION,
                    action='deny_data_transfer',
                    multilingual_context=MultilingualAuditContext(),
                    severity=AuditSeverity.WARNING,
                    additional_details={
                        'request_id': request_id,
                        'source_region': request.source_region.value,
                        'destination_region': request.destination_region.value,
                        'reason': reason
                    }
                )
                
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to deny transfer request: {e}")
                return False
    
    def get_compliance_rules_for_language(self, language: str) -> List[RegionalComplianceRule]:
        """
        Get all compliance rules applicable to a language.
        
        Args:
            language: Language code
            
        Returns:
            List of applicable compliance rules
        """
        with self._lock:
            return [
                rule for rule in self._compliance_rules.values()
                if language in rule.languages
            ]
    
    def generate_residency_report(self,
                                 region: Optional[DataResidencyRegion] = None,
                                 language: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive data residency report.
        
        Args:
            region: Optional region to filter by
            language: Optional language to filter by
            
        Returns:
            Comprehensive residency report
        """
        with self._lock:
            try:
                # Filter requirements
                requirements = list(self._requirements.values())
                if region:
                    requirements = [r for r in requirements if r.region == region]
                if language:
                    requirements = [r for r in requirements if language in r.languages]
                
                # Filter compliance rules
                rules = list(self._compliance_rules.values())
                if region:
                    rules = [r for r in rules if r.region == region]
                if language:
                    rules = [r for r in rules if language in r.languages]
                
                # Filter transfer requests
                transfers = list(self._transfer_requests.values())
                if region:
                    transfers = [t for t in transfers 
                               if t.source_region == region or t.destination_region == region]
                if language:
                    transfers = [t for t in transfers if t.language == language]
                
                report = {
                    'report_generated_at': datetime.now(timezone.utc).isoformat(),
                    'filters': {
                        'region': region.value if region else 'all',
                        'language': language if language else 'all'
                    },
                    'summary': {
                        'total_requirements': len(requirements),
                        'total_compliance_rules': len(rules),
                        'total_transfer_requests': len(transfers),
                        'approved_transfers': sum(1 for t in transfers if t.approved),
                        'pending_transfers': sum(1 for t in transfers if not t.approved)
                    },
                    'requirements': [r.to_dict() for r in requirements],
                    'compliance_rules': [r.to_dict() for r in rules],
                    'transfer_requests': [t.to_dict() for t in transfers],
                    'language_region_mapping': {
                        lang: region.value 
                        for lang, region in self._language_region_map.items()
                        if not language or lang == language
                    }
                }
                
                # Log report generation
                self.audit_logger.log_multilingual_event(
                    event_type=MultilingualEventType.MULTILINGUAL_CONFIGURATION_LOADED,
                    action='generate_residency_report',
                    multilingual_context=MultilingualAuditContext(
                        original_language=language or 'en'
                    ),
                    severity=AuditSeverity.INFO,
                    additional_details={
                        'region': region.value if region else 'all',
                        'language': language if language else 'all',
                        'requirements_count': len(requirements),
                        'rules_count': len(rules)
                    }
                )
                
                return report
                
            except Exception as e:
                self.logger.error(f"Failed to generate residency report: {e}")
                return {
                    'error': str(e),
                    'report_generated_at': datetime.now(timezone.utc).isoformat()
                }
    
    def get_residency_statistics(self) -> Dict[str, Any]:
        """Get comprehensive data residency statistics."""
        with self._lock:
            return {
                **self._residency_stats,
                'requirements_by_region': {
                    region.value: sum(1 for r in self._requirements.values() if r.region == region)
                    for region in DataResidencyRegion
                },
                'rules_by_region': {
                    region.value: sum(1 for r in self._compliance_rules.values() if r.region == region)
                    for region in DataResidencyRegion
                },
                'languages_by_region': {
                    region.value: [lang for lang, reg in self._language_region_map.items() if reg == region]
                    for region in DataResidencyRegion
                }
            }
