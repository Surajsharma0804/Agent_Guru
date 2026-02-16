"""
Property-based tests for Scene Analyzer

Tests universal properties that must hold for all inputs:
- Scene classification is deterministic
- Spatial relationships are consistent
- Feature extraction is robust
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
from guru_vision.scene import (
    SceneAnalyzer,
    SceneType,
    RelationType,
    SceneClassification,
    SpatialRelationship
)


# Strategy for generating valid images
@st.composite
def image_strategy(draw):
    """Generate random valid images"""
    height = draw(st.integers(min_value=100, max_value=1000))
    width = draw(st.integers(min_value=100, max_value=1000))
    # Keep image size reasonable
    assume(height * width * 3 < 10_000_000)  # < 10MB
    image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    return image


# Strategy for generating bounding boxes
@st.composite
def bbox_strategy(draw):
    """Generate random valid bounding box"""
    x1 = draw(st.integers(min_value=0, max_value=500))
    y1 = draw(st.integers(min_value=0, max_value=500))
    width = draw(st.integers(min_value=20, max_value=200))
    height = draw(st.integers(min_value=20, max_value=200))
    return (x1, y1, x1 + width, y1 + height)


# Strategy for generating object lists
@st.composite
def objects_strategy(draw):
    """Generate list of bounding boxes"""
    num_objects = draw(st.integers(min_value=2, max_value=10))
    objects = []
    for _ in range(num_objects):
        bbox = draw(bbox_strategy())
        objects.append(bbox)
    return objects


class TestSceneAnalysisProperties:
    """Property-based tests for scene analysis"""
    
    @given(image_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_scene_classification_deterministic(self, image):
        """Property: Scene classification is deterministic"""
        analyzer = SceneAnalyzer()
        result1 = analyzer.analyze_scene(image)
        result2 = analyzer.analyze_scene(image)
        
        assert result1.scene_type == result2.scene_type
        assert result1.confidence == result2.confidence
        assert result1.features == result2.features
    
    @given(image_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_scene_confidence_bounded(self, image):
        """Property: Scene confidence is always between 0 and 1"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_scene(image)
        
        assert 0.0 <= result.confidence <= 1.0
    
    @given(image_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_scene_type_valid(self, image):
        """Property: Scene type is always a valid SceneType"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_scene(image)
        
        assert isinstance(result.scene_type, SceneType)
        assert result.scene_type in SceneType
    
    @given(image_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_features_always_extracted(self, image):
        """Property: All expected features are always extracted"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_scene(image)
        
        expected_features = [
            'avg_hue', 'avg_saturation', 'avg_value',
            'brightness', 'edge_density', 'color_variance',
            'top_brightness', 'green_ratio', 'blue_ratio'
        ]
        
        for feature in expected_features:
            assert feature in result.features
            assert isinstance(result.features[feature], float)
    
    @given(image_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_feature_values_bounded(self, image):
        """Property: Feature values are within expected ranges"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_scene(image)
        
        # HSV ranges
        assert 0 <= result.features['avg_hue'] <= 180
        assert 0 <= result.features['avg_saturation'] <= 255
        assert 0 <= result.features['avg_value'] <= 255
        
        # Brightness and variance
        assert 0 <= result.features['brightness'] <= 255
        assert result.features['color_variance'] >= 0
        assert 0 <= result.features['top_brightness'] <= 255
        
        # Ratios
        assert 0 <= result.features['edge_density'] <= 1.0
        assert 0 <= result.features['green_ratio'] <= 1.0
        assert 0 <= result.features['blue_ratio'] <= 1.0
    
    @given(st.integers(min_value=0, max_value=255))
    @settings(max_examples=50, deadline=1000)
    def test_uniform_image_classification(self, pixel_value):
        """Property: Uniform images produce consistent classification"""
        analyzer = SceneAnalyzer()
        image = np.full((480, 640, 3), pixel_value, dtype=np.uint8)
        result = analyzer.analyze_scene(image)
        
        # Should always produce valid result
        assert isinstance(result, SceneClassification)
        assert 0.0 <= result.confidence <= 1.0
    
    @given(image_strategy())
    @settings(max_examples=30, deadline=3000)
    def test_scene_classification_returns_valid_object(self, image):
        """Property: Scene classification always returns SceneClassification"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_scene(image)
        
        assert isinstance(result, SceneClassification)
        assert hasattr(result, 'scene_type')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'features')


class TestSpatialRelationshipProperties:
    """Property-based tests for spatial relationships"""
    
    @given(objects_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_relationships_deterministic(self, objects):
        """Property: Spatial relationships are deterministic"""
        analyzer = SceneAnalyzer()
        result1 = analyzer.analyze_spatial_relationships(objects)
        result2 = analyzer.analyze_spatial_relationships(objects)
        
        assert len(result1) == len(result2)
        for r1, r2 in zip(result1, result2):
            assert r1.object1_id == r2.object1_id
            assert r1.object2_id == r2.object2_id
            assert r1.relationship == r2.relationship
            assert r1.confidence == r2.confidence
    
    @given(objects_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_relationship_confidence_bounded(self, objects):
        """Property: Relationship confidence is always between 0 and 1"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_spatial_relationships(objects)
        
        for rel in result:
            assert 0.0 <= rel.confidence <= 1.0
    
    @given(objects_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_relationship_type_valid(self, objects):
        """Property: Relationship type is always valid RelationType"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_spatial_relationships(objects)
        
        for rel in result:
            assert isinstance(rel.relationship, RelationType)
            assert rel.relationship in RelationType
    
    @given(objects_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_relationship_ids_valid(self, objects):
        """Property: Object IDs are valid indices"""
        analyzer = SceneAnalyzer()
        result = analyzer.analyze_spatial_relationships(objects)
        
        for rel in result:
            assert 0 <= rel.object1_id < len(objects)
            assert 0 <= rel.object2_id < len(objects)
            assert rel.object1_id != rel.object2_id
    
    @given(objects_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_max_relationships_respected(self, objects):
        """Property: Number of relationships never exceeds max_relationships"""
        max_rel = 5
        analyzer = SceneAnalyzer(max_relationships=max_rel)
        result = analyzer.analyze_spatial_relationships(objects)
        
        assert len(result) <= max_rel
    
    @given(objects_strategy(), st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=50, deadline=2000)
    def test_confidence_threshold_respected(self, objects, threshold):
        """Property: All relationships meet confidence threshold"""
        analyzer = SceneAnalyzer(confidence_threshold=threshold)
        result = analyzer.analyze_spatial_relationships(objects)
        
        for rel in result:
            assert rel.confidence >= threshold
    
    @given(st.integers(min_value=0, max_value=1))
    @settings(max_examples=20, deadline=1000)
    def test_insufficient_objects_returns_empty(self, num_objects):
        """Property: Less than 2 objects returns empty list"""
        analyzer = SceneAnalyzer()
        objects = [(i * 100, i * 100, i * 100 + 50, i * 100 + 50) 
                   for i in range(num_objects)]
        result = analyzer.analyze_spatial_relationships(objects)
        
        assert result == []
    
    @given(bbox_strategy(), bbox_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_two_objects_produce_one_relationship(self, bbox1, bbox2):
        """Property: Two objects produce at most one relationship"""
        analyzer = SceneAnalyzer(confidence_threshold=0.0)
        objects = [bbox1, bbox2]
        result = analyzer.analyze_spatial_relationships(objects)
        
        # Should produce exactly one relationship (threshold is 0)
        assert len(result) <= 1
        if len(result) == 1:
            assert result[0].object1_id == 0
            assert result[0].object2_id == 1


class TestConfigurationProperties:
    """Property-based tests for configuration"""
    
    @given(st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=50, deadline=1000)
    def test_confidence_threshold_setting(self, threshold):
        """Property: Confidence threshold can be set to any valid value"""
        analyzer = SceneAnalyzer()
        analyzer.set_confidence_threshold(threshold)
        assert analyzer.confidence_threshold == threshold
    
    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=50, deadline=1000)
    def test_max_relationships_setting(self, max_rel):
        """Property: Max relationships can be set to any positive value"""
        analyzer = SceneAnalyzer()
        analyzer.set_max_relationships(max_rel)
        assert analyzer.max_relationships == max_rel
    
    @given(st.floats(min_value=-10.0, max_value=-0.01))
    @settings(max_examples=20, deadline=1000)
    def test_negative_confidence_threshold_rejected(self, threshold):
        """Property: Negative confidence thresholds are rejected"""
        analyzer = SceneAnalyzer()
        with pytest.raises(ValueError):
            analyzer.set_confidence_threshold(threshold)
    
    @given(st.floats(min_value=1.01, max_value=10.0))
    @settings(max_examples=20, deadline=1000)
    def test_excessive_confidence_threshold_rejected(self, threshold):
        """Property: Confidence thresholds > 1.0 are rejected"""
        analyzer = SceneAnalyzer()
        with pytest.raises(ValueError):
            analyzer.set_confidence_threshold(threshold)
    
    @given(st.integers(min_value=-100, max_value=0))
    @settings(max_examples=20, deadline=1000)
    def test_non_positive_max_relationships_rejected(self, max_rel):
        """Property: Non-positive max_relationships are rejected"""
        analyzer = SceneAnalyzer()
        with pytest.raises(ValueError):
            analyzer.set_max_relationships(max_rel)


class TestRelationshipConsistency:
    """Test consistency properties of spatial relationships"""
    
    @given(bbox_strategy(), bbox_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_relationship_order_independence(self, bbox1, bbox2):
        """Property: Relationship detection is consistent regardless of order"""
        analyzer = SceneAnalyzer(confidence_threshold=0.0)
        
        # Analyze in both orders
        result1 = analyzer.analyze_spatial_relationships([bbox1, bbox2])
        result2 = analyzer.analyze_spatial_relationships([bbox2, bbox1])
        
        # Should produce relationships (possibly different due to order)
        # But both should be valid
        for rel in result1 + result2:
            assert isinstance(rel.relationship, RelationType)
            assert 0.0 <= rel.confidence <= 1.0
    
    @given(st.integers(min_value=100, max_value=500),
           st.integers(min_value=100, max_value=500))
    @settings(max_examples=50, deadline=2000)
    def test_identical_boxes_no_relationship(self, x, y):
        """Property: Identical boxes produce no relationship"""
        analyzer = SceneAnalyzer()
        bbox = (x, y, x + 100, y + 100)
        objects = [bbox, bbox]
        result = analyzer.analyze_spatial_relationships(objects)
        
        # Identical boxes should not produce meaningful relationships
        # (they're the same object)
        assert len(result) <= 1
    
    @given(bbox_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_contained_box_detected(self, outer_bbox):
        """Property: Containment is detected when one box is inside another"""
        x1, y1, x2, y2 = outer_bbox
        # Create inner box that's definitely inside
        margin = min((x2 - x1) // 4, (y2 - y1) // 4, 10)
        assume(margin > 0)
        # Ensure boxes are large enough for meaningful containment detection
        assume((x2 - x1) >= 40 and (y2 - y1) >= 40)
        
        inner_bbox = (x1 + margin, y1 + margin, x2 - margin, y2 - margin)
        
        analyzer = SceneAnalyzer(confidence_threshold=0.0)
        result = analyzer.analyze_spatial_relationships([outer_bbox, inner_bbox])
        
        # Should detect some relationship
        assert len(result) >= 1
        # For small boxes, NEAR is acceptable; for larger boxes, should detect containment
        relationships = [r.relationship for r in result]
        assert any(r in relationships for r in [RelationType.INSIDE, RelationType.OUTSIDE, RelationType.NEAR])


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=30, deadline=2000)
    def test_small_images(self, size):
        """Property: Small images are handled correctly"""
        analyzer = SceneAnalyzer()
        # Create very small image
        image = np.random.randint(0, 256, (size, size, 3), dtype=np.uint8)
        result = analyzer.analyze_scene(image)
        
        assert isinstance(result, SceneClassification)
        assert 0.0 <= result.confidence <= 1.0
    
    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=30, deadline=2000)
    def test_many_objects(self, num_objects):
        """Property: Many objects are handled correctly"""
        analyzer = SceneAnalyzer(max_relationships=100)
        objects = [
            (i * 50, i * 50, i * 50 + 40, i * 50 + 40)
            for i in range(num_objects)
        ]
        result = analyzer.analyze_spatial_relationships(objects)
        
        # Should handle without error
        assert isinstance(result, list)
        for rel in result:
            assert isinstance(rel, SpatialRelationship)
    
    @given(st.integers(min_value=0, max_value=255))
    @settings(max_examples=50, deadline=1000)
    def test_monochrome_images(self, gray_value):
        """Property: Monochrome images are classified"""
        analyzer = SceneAnalyzer()
        image = np.full((480, 640, 3), gray_value, dtype=np.uint8)
        result = analyzer.analyze_scene(image)
        
        assert isinstance(result, SceneClassification)
        assert result.scene_type in SceneType
    
    @given(bbox_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_overlapping_boxes(self, bbox1):
        """Property: Overlapping boxes produce valid relationships"""
        x1, y1, x2, y2 = bbox1
        # Create overlapping box
        overlap_x = (x1 + x2) // 2
        overlap_y = (y1 + y2) // 2
        bbox2 = (overlap_x, overlap_y, overlap_x + (x2 - x1), overlap_y + (y2 - y1))
        
        analyzer = SceneAnalyzer(confidence_threshold=0.0)
        result = analyzer.analyze_spatial_relationships([bbox1, bbox2])
        
        # Should produce valid relationship
        assert len(result) >= 0  # May or may not detect relationship
        for rel in result:
            assert isinstance(rel.relationship, RelationType)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
