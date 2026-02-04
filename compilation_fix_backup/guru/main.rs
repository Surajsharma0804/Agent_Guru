//! # AGENT_GURU Main Entry Point
//! 
//! Production-grade sovereign AI operating companion with cryptographic governance.

use agent_guru;
use std::process;

fn main() {
    // Initialize the system
    if let Err(e) = agent_guru::init() {
        eprintln!("Failed to initialize AGENT_GURU: {}", e);
        process::exit(1);
    }
    
    println!("AGENT_GURU {} initialized successfully", agent_guru::VERSION);
    println!("System ready for operation");
}