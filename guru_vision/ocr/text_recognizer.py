"""
Text Recognition Module

Provides OCR capabilities using EasyOCR or Tesseract.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RecognizedText:
    """Represents recognized text with location and confidence"""
    text: str
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    language: str = 'en'


class TextRecognizer:
    """
    Text recognition using EasyOCR or Tesseract.
    
    Supports 100+ languages with configurable confidence thresholds.
    """
    
    def __init__(self,
                 languages: List[str] = None,
                 confidence_threshold: float = 0.5,
                 use_gpu: bool = False):
        """
        Initialize text recognizer.
        
        Args:
            languages: List of language codes (default: ['en'])
            confidence_threshold: Minimum confidence for text detection
            use_gpu: Whether to use GPU acceleration
        """
        self.languages = languages or ['en']
        self.confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self.use_gpu = use_gpu
        self.reader = None
        
        self._initialize_reader()
    
    def _initialize_reader(self) -> None:
        """Initialize EasyOCR reader"""
        try:
            import easyocr
            self.reader = easyocr.Reader(
                self.languages,
                gpu=self.use_gpu,
                verbose=False
            )
            logger.info(f"EasyOCR initialized with languages: {self.languages}")
        except ImportError:
            logger.warning("EasyOCR not available. Install with: pip install easyocr")
            self.reader = None
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            self.reader = None
    
    def recognize(self, image: np.ndarray) -> List[RecognizedText]:
        """
        Recognize text in image.
        
        Args:
            image: Input image as numpy array (H, W, 3)
        
        Returns:
            List of recognized text with bounding boxes
        """
        if self.reader is None:
            logger.warning("OCR reader not initialized")
            return []
        
        if image is None or image.size == 0:
            return []
        
        try:
            # Run OCR
            results = self.reader.readtext(image)
            
            # Parse results
            recognized_texts = []
            for bbox, text, confidence in results:
                if confidence >= self.confidence_threshold:
                    # Convert bbox format: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]] -> (x1, y1, x2, y2)
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    x1, x2 = int(min(x_coords)), int(max(x_coords))
                    y1, y2 = int(min(y_coords)), int(max(y_coords))
                    
                    recognized_texts.append(RecognizedText(
                        text=text,
                        bbox=(x1, y1, x2, y2),
                        confidence=float(confidence),
                        language=self.languages[0]  # Primary language
                    ))
            
            return recognized_texts
            
        except Exception as e:
            logger.error(f"OCR recognition failed: {e}")
            return []
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set confidence threshold.
        
        Args:
            threshold: New confidence threshold (0.0 to 1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        self.confidence_threshold = threshold
    
    def set_languages(self, languages: List[str]) -> None:
        """
        Set recognition languages.
        
        Args:
            languages: List of language codes
        """
        if not languages:
            raise ValueError("At least one language must be specified")
        
        self.languages = languages
        self._initialize_reader()
