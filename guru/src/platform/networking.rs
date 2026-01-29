//! Networking Abstraction
//! Transport layer for Sync.

use std::fs;
use std::io::{self, Write};


#[derive(Debug, Clone)]
pub struct TransportPacket {
    pub data: Vec<u8>,
    pub metadata: String,
}

pub trait NetworkTransport: Send + Sync {
    fn send(&self, packet: &TransportPacket) -> io::Result<()>;
    fn receive_all(&self) -> io::Result<Vec<TransportPacket>>;
}

// File-based transport (e.g. Shared Folder / USB)
pub struct FileTransport {
    pub base_path: String,
}

impl FileTransport {
    pub fn new(path: &str) -> Self {
        fs::create_dir_all(path).ok();
        Self { base_path: path.to_string() }
    }
}

impl NetworkTransport for FileTransport {
    fn send(&self, packet: &TransportPacket) -> io::Result<()> {
        // Name: timestamp_random.sync
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
            
        let fname = format!("{}/{}.sync", self.base_path, timestamp);
        let mut file = fs::File::create(fname)?;
        
        // Format: [MetaLen: u32][Meta bytes][Data...]
        let m_bytes = packet.metadata.as_bytes();
        file.write_all(&(m_bytes.len() as u32).to_le_bytes())?;
        file.write_all(m_bytes)?;
        file.write_all(&packet.data)?;
        
        Ok(())
    }

    fn receive_all(&self) -> io::Result<Vec<TransportPacket>> {
        let mut packets = Vec::new();
        
        for entry in fs::read_dir(&self.base_path)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().map(|s| s == "sync").unwrap_or(false) {
                let content = fs::read(&path)?;
                if content.len() < 4 { continue; }
                
                let m_len = u32::from_le_bytes(content[0..4].try_into().unwrap()) as usize;
                if 4 + m_len > content.len() { continue; }
                
                let meta = String::from_utf8(content[4..4+m_len].to_vec()).unwrap_or_default();
                let data = content[4+m_len..].to_vec();
                
                packets.push(TransportPacket { metadata: meta, data });
                
                // Rename or delete after read? 
                // For now, keep. Or rename to .processed
            }
        }
        
        Ok(packets)
    }
}
