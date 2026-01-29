use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{self, BufRead, BufReader};
use std::path::Path;

pub struct Tokenizer {
    encoder: HashMap<String, usize>,
    decoder: HashMap<usize, String>,
    bpe_ranks: HashMap<(String, String), usize>,
    cache: HashMap<String, String>,
}

impl Tokenizer {
    pub fn new<P: AsRef<Path>>(vocab_path: P, merges_path: P) -> io::Result<Self> {
        // Load vocab.json (token -> id)
        // For now, simpler: we assume we have a merges file and we build vocab from it + base bytes?
        // Whisper uses a specific vocab. 
        // Let's implement the structure assuming we load standard GPT-2 style files.
        
        let mut encoder = HashMap::new();
        let mut decoder = HashMap::new();
        let mut bpe_ranks = HashMap::new();

        // Placeholder for loading logic
        // In prod we parse "vocab.json" and "merges.txt"
        
        Ok(Self {
            encoder,
            decoder,
            bpe_ranks,
            cache: HashMap::new(),
        })
    }

    fn bpe(&self, token: &str) -> String {
        // Apply BPE merges to a word
        if self.cache.contains_key(token) {
            return self.cache.get(token).unwrap().clone();
        }
        
        // TODO: Implement actual merge loop
        // 1. Split into chars
        // 2. Find best pair
        // 3. Merge
        // 4. Repeat
        
        token.to_string()
    }

    pub fn encode(&self, text: &str) -> Vec<usize> {
        // 1. Normalize
        // 2. Regex split
        // 3. Map to bytes
        // 4. BPE
        // 5. Map to IDs
        vec![]
    }

    pub fn decode(&self, tokens: &[usize]) -> String {
        let mut text = String::new();
        for &t in tokens {
            if let Some(s) = self.decoder.get(&t) {
                text.push_str(s);
            }
        }
        text
    }
}
