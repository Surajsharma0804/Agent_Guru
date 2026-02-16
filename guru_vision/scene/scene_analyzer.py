"""
Scene Understanding Module

Provides scene classification and spatial relationship analysis.
"""

import numpy as np
import cv2
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SceneType(Enum):
    """Scene types for classification"""
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    OFFICE = "office"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    LIVING_ROOM = "living_room"
    STREET = "street"
    PARK = "park"
    BEACH = "beach"
    MOUNTAIN = "mountain"
    FOREST = "forest"
    URBAN = "urban"
    RURAL = "rural"
    UNKNOWN = "unknown"


class RelationType(Enum):
    """Spatial relationship types"""
    ABOVE = "above"
    BELOW = "below"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    NEAR = "near"
    FAR = "far"
    INSIDE = "inside"
    OUTSIDE = "outside"
    TOUCHING = "touching"


@dataclass
class SceneClassification:
    """Scene classification result"""
    scene_type: SceneType
    confidence: float
    features: Dict[str, float]  # Color, texture, density features


@dataclass
class SpatialRelationship:
    """Spatial relationship between objects"""
    object1_id: int
    object2_id: int
    relationship: RelationType
    confidence: float


class SceneAnalyzer:
    """
    Scene understanding with classification and spatial analysis.
    
    Analyzes scenes to determine type (indoor/outdoor, specific locations)
    and spatial relationships between objects.
    """
    
    def __init__(self,
                 confidence_threshold: float = 0.5,
                 max_relationships: int = 10):
        """
        Initialize scene analyzer.
        
        Args:
            confidence_threshold: Minimum confidence for classification
            max_relationships: Maximum spatial relationships to compute
        """
        self.confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self.max_relationships = max(1, max_relationships)
    
    def analyze_scene(self, image: np.ndarray) -> SceneClassification:
        """
        Analyze scene and classify type.
        
        Args:
            image: Input image as numpy array (H, W, 3)
        
        Returns:
            SceneClassification with type and features
        """
        if image is None or image.size == 0:
            return SceneClassification(
                scene_type=SceneType.UNKNOWN,
                confidence=0.0,
                features={}
            )
        
        try:
            # Extract features
            features = self._extract_features(image)
            
            # Classify scene
            scene_type, confidence = self._classify_scene(features)
            
            return SceneClassification(
                scene_type=scene_type,
                confidence=confidence,
                features=features
            )
            
        except Exception as e:
            logger.error(f"Scene analysis failed: {e}")
            return SceneClassification(
                scene_type=SceneType.UNKNOWN,
                confidence=0.0,
                features={}
            )
    
    def analyze_spatial_relationships(
        self,
        objects: List[Tuple[int, int, int, int]]  # List of bboxes (x1, y1, x2, y2)
    ) -> List[SpatialRelationship]:
        """
        Analyze spatial relationships between objects.
        
        Args:
            objects: List of object bounding boxes
        
        Returns:
            List of spatial relationships
        """
        if not objects or len(objects) < 2:
            return []
        
        relationships = []
        
        # Compute relationships between pairs
        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                if len(relationships) >= self.max_relationships:
                    break
                
                rel_type, confidence = self._compute_relationship(
                    objects[i], objects[j]
                )
                
                if confidence >= self.confidence_threshold:
                    relationships.append(SpatialRelationship(
                        object1_id=i,
                        object2_id=j,
                        relationship=rel_type,
                        confidence=confidence
                    ))
        
        return relationships
    
    def _extract_features(self, image: np.ndarray) -> Dict[str, float]:
        """
        Extract scene features.
        
        Args:
            image: Input image
        
        Returns:
            Dictionary of features
        """
        features = {}
        
        # Color features
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        features['avg_hue'] = float(np.mean(hsv[:, :, 0]))
        features['avg_saturation'] = float(np.mean(hsv[:, :, 1]))
        features['avg_value'] = float(np.mean(hsv[:, :, 2]))
        
        # Brightness
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        features['brightness'] = float(np.mean(gray))
        
        # Texture (edge density)
        edges = cv2.Canny(gray, 50, 150)
        features['edge_density'] = float(np.sum(edges > 0) / edges.size)
        
        # Color variance
        features['color_variance'] = float(np.std(gray))
        
        # Sky detection (top third brightness)
        top_third = gray[:gray.shape[0]//3, :]
        features['top_brightness'] = float(np.mean(top_third))
        
        # Green detection (vegetation)
        green_mask = (hsv[:, :, 0] > 35) & (hsv[:, :, 0] < 85)
        features['green_ratio'] = float(np.sum(green_mask) / green_mask.size)
        
        # Blue detection (sky/water)
        blue_mask = (hsv[:, :, 0] > 90) & (hsv[:, :, 0] < 130)
        features['blue_ratio'] = float(np.sum(blue_mask) / blue_mask.size)
        
        return features
    
    def _classify_scene(self, features: Dict[str, float]) -> Tuple[SceneType, float]:
        """
        Classify scene based on features.
        
        Args:
            features: Extracted features
        
        Returns:
            Tuple of (scene_type, confidence)
        """
        # Simple rule-based classification
        # In production, this would use a trained model
        
        brightness = features.get('brightness', 0)
        edge_density = features.get('edge_density', 0)
        green_ratio = features.get('green_ratio', 0)
        blue_ratio = features.get('blue_ratio', 0)
        top_brightness = features.get('top_brightness', 0)
        
        # Outdoor detection
        if top_brightness > 150 and blue_ratio > 0.2:
            # Likely outdoor with sky
            if green_ratio > 0.3:
                return SceneType.PARK, 0.8
            elif blue_ratio > 0.4:
                return SceneType.BEACH, 0.75
            else:
                return SceneType.OUTDOOR, 0.7
        
        # Forest/nature
        if green_ratio > 0.4:
            return SceneType.FOREST, 0.75
        
        # Indoor detection
        if brightness < 100 or edge_density > 0.15:
            # Likely indoor
            if edge_density > 0.2:
                return SceneType.OFFICE, 0.7
            else:
                return SceneType.INDOOR, 0.65
        
        # Urban
        if edge_density > 0.18:
            return SceneType.URBAN, 0.7
        
        # Default
        return SceneType.UNKNOWN, 0.5
    
    def _compute_relationship(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> Tuple[RelationType, float]:
        """
        Compute spatial relationship between two bounding boxes.
        
        Args:
            bbox1: First bounding box (x1, y1, x2, y2)
            bbox2: Second bounding box (x1, y1, x2, y2)
        
        Returns:
            Tuple of (relationship_type, confidence)
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate centers
        cx1, cy1 = (x1_1 + x2_1) / 2, (y1_1 + y2_1) / 2
        cx2, cy2 = (x1_2 + x2_2) / 2, (y1_2 + y2_2) / 2
        
        # Calculate distance
        distance = np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)
        
        # Calculate box sizes
        size1 = max(x2_1 - x1_1, y2_1 - y1_1)
        size2 = max(x2_2 - x1_2, y2_2 - y1_2)
        avg_size = (size1 + size2) / 2
        
        # Vertical relationship
        if abs(cx1 - cx2) < avg_size * 0.3:  # Roughly aligned horizontally
            if cy1 < cy2 - avg_size * 0.2:
                return RelationType.ABOVE, 0.9
            elif cy1 > cy2 + avg_size * 0.2:
                return RelationType.BELOW, 0.9
        
        # Horizontal relationship
        if abs(cy1 - cy2) < avg_size * 0.3:  # Roughly aligned vertically
            if cx1 < cx2 - avg_size * 0.2:
                return RelationType.LEFT_OF, 0.9
            elif cx1 > cx2 + avg_size * 0.2:
                return RelationType.RIGHT_OF, 0.9
        
        # Distance-based relationships
        if distance < avg_size * 0.5:
            return RelationType.NEAR, 0.85
        elif distance > avg_size * 3:
            return RelationType.FAR, 0.8
        
        # Check for containment
        if (x1_1 <= x1_2 and y1_1 <= y1_2 and x2_1 >= x2_2 and y2_1 >= y2_2):
            return RelationType.INSIDE, 0.95
        elif (x1_2 <= x1_1 and y1_2 <= y1_1 and x2_2 >= x2_1 and y2_2 >= y2_1):
            return RelationType.OUTSIDE, 0.95
        
        # Default: near
        return RelationType.NEAR, 0.6
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set confidence threshold.
        
        Args:
            threshold: New confidence threshold (0.0 to 1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        self.confidence_threshold = threshold
    
    def set_max_relationships(self, max_relationships: int) -> None:
        """
        Set maximum number of relationships to compute.
        
        Args:
            max_relationships: Maximum relationships (must be positive)
        """
        if max_relationships < 1:
            raise ValueError("max_relationships must be at least 1")
        self.max_relationships = max_relationships
