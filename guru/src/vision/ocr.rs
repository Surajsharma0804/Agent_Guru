//! OCR (Optical Character Recognition)
//! Interface for text extraction from images.

use super::image_processing::ImageBuffer;

pub trait OCRModel {
    fn recognize_text(&self, image: &ImageBuffer) -> String;
}

pub struct MockOCR;

impl OCRModel for MockOCR {
    fn recognize_text(&self, _image: &ImageBuffer) -> String {
        // Placeholder for future Tesseract integration
        "Agent Guru Vision System Online".to_string()
    }
}
