//! Image Processing
//! Basic bitmap manipulation.


use std::fs::File;
use std::io::Write;

#[derive(Debug, Clone)]
pub struct ImageBuffer {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<u8>, // BGRA or RGBA usually (Windows GDI is BGRA)
}

impl ImageBuffer {
    pub fn new(width: u32, height: u32, pixels: Vec<u8>) -> Self {
        Self { width, height, pixels }
    }

    pub fn to_grayscale(&self) -> ImageBuffer {
        // Assume BGRA (4 bytes)
        let mut gray_pixels = Vec::with_capacity((self.width * self.height) as usize);
        
        for chunk in self.pixels.chunks(4) {
             if chunk.len() >= 3 {
                 let b = chunk[0] as f32;
                 let g = chunk[1] as f32;
                 let r = chunk[2] as f32;
                 // Luminance formula
                 let y = (0.299 * r + 0.587 * g + 0.114 * b) as u8;
                 gray_pixels.push(y);
             }
        }
        
        ImageBuffer {
            width: self.width,
            height: self.height,
            pixels: gray_pixels, // 1 byte per pixel
        }
    }
    
    pub fn save_bmp(&self, path: &str) -> std::io::Result<()> {
        let mut file = File::create(path)?;
        
        let file_size = 14 + 40 + self.pixels.len() as u32;
        
        // Bitmap File Header
        file.write_all(b"BM")?;
        file.write_all(&file_size.to_le_bytes())?;
        file.write_all(&[0, 0, 0, 0])?; // Reserved
        file.write_all(&54u32.to_le_bytes())?; // Offset
        
        // DIB Header
        file.write_all(&40u32.to_le_bytes())?; // Header Size
        file.write_all(&(self.width as i32).to_le_bytes())?;
        file.write_all(&(-(self.height as i32)).to_le_bytes())?; // Top-down
        file.write_all(&1u16.to_le_bytes())?; // Planes
        
        // BitCount
        let bpp = if self.pixels.len() == (self.width * self.height) as usize { 8 } else { 32 };
        file.write_all(&(bpp as u16).to_le_bytes())?;
        
        file.write_all(&0u32.to_le_bytes())?; // Compression
        file.write_all(&0u32.to_le_bytes())?; // SizeImage unknown
        file.write_all(&0u32.to_le_bytes())?; // X
        file.write_all(&0u32.to_le_bytes())?; // Y
        file.write_all(&0u32.to_le_bytes())?; // Colors
        file.write_all(&0u32.to_le_bytes())?; // Important
        
        // Palette for grayscale
        if bpp == 8 {
             for i in 0..256 {
                 file.write_all(&[i as u8, i as u8, i as u8, 0])?;
             }
        }
        
        file.write_all(&self.pixels)?;
        Ok(())
    }
}
