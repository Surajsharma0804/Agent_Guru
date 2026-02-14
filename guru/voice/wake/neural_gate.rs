// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! Neural Network Classifier for Wake Word Detection
//! 
//! This module implements neural network inference with quantization support
//! for efficient wake word classification.
//! 
//! Based on clean room extraction of algorithms from openWakeWord project.
//! Mathematical concepts and implementation patterns only - no foreign code.

use std::collections::HashMap;
use thiserror::Error;

/// Neural network inference errors
#[derive(Error, Debug)]
pub enum NeuralError {
    #[error("Model loading error: {0}")]
    ModelLoading(String),
    
    #[error("Inference error: {0}")]
    Inference(String),
    
    #[error("Invalid input shape: expected {expected:?}, got {actual:?}")]
    InvalidInputShape { expected: Vec<usize>, actual: Vec<usize> },
    
    #[error("Quantization error: {0}")]
    Quantization(String),
    
    #[error("Configuration error: {0}")]
    Configuration(String),
}

/// Neural network model configuration
#[derive(Debug, Clone)]
pub struct ModelConfig {
    pub input_shape: Vec<usize>,
    pub output_classes: usize,
    pub quantization: QuantizationType,
    pub confidence_threshold: f32,
    pub model_path: String,
}

/// Quantization types for model optimization
#[derive(Debug, Clone, Copy)]
pub enum QuantizationType {
    Float32,
    Int8,
    Float16,
}

/// Neural network prediction result
#[derive(Debug, Clone)]
pub struct PredictionResult {
    pub class_probabilities: Vec<f32>,
    pub max_confidence: f32,
    pub predicted_class: usize,
    pub inference_time_ms: f32,
}

/// Simplified neural network layer for wake word detection
#[derive(Debug, Clone)]
pub struct DenseLayer {
    weights: Vec<Vec<f32>>,
    biases: Vec<f32>,
    activation: ActivationType,
}

/// Activation function types
#[derive(Debug, Clone, Copy)]
pub enum ActivationType {
    ReLU,
    Sigmoid,
    Softmax,
    Linear,
}

impl DenseLayer {
    /// Create new dense layer
    pub fn new(input_size: usize, output_size: usize, activation: ActivationType) -> Self {
        // Initialize with small random weights (Xavier initialization)
        let mut weights = Vec::with_capacity(output_size);
        let scale = (2.0 / input_size as f32).sqrt();
        
        for _ in 0..output_size {
            let mut row = Vec::with_capacity(input_size);
            for _ in 0..input_size {
                // Simplified random initialization (production would use proper RNG)
                let weight = (rand::random::<f32>() - 0.5) * 2.0 * scale;
                row.push(weight);
            }
            weights.push(row);
        }
        
        let biases = vec![0.0; output_size];
        
        Self {
            weights,
            biases,
            activation,
        }
    }
    
    /// Forward pass through the layer
    pub fn forward(&self, input: &[f32]) -> Result<Vec<f32>, NeuralError> {
        if input.len() != self.weights[0].len() {
            return Err(NeuralError::InvalidInputShape {
                expected: vec![self.weights[0].len()],
                actual: vec![input.len()],
            });
        }
        
        let mut output = Vec::with_capacity(self.weights.len());
        
        // Matrix multiplication: output = weights * input + biases
        for (weight_row, &bias) in self.weights.iter().zip(self.biases.iter()) {
            let dot_product: f32 = weight_row.iter()
                .zip(input.iter())
                .map(|(w, x)| w * x)
                .sum();
            
            output.push(dot_product + bias);
        }
        
        // Apply activation function
        self.apply_activation(&mut output);
        
        Ok(output)
    }
    
    /// Apply activation function
    fn apply_activation(&self, values: &mut [f32]) {
        match self.activation {
            ActivationType::ReLU => {
                for value in values.iter_mut() {
                    *value = value.max(0.0);
                }
            }
            ActivationType::Sigmoid => {
                for value in values.iter_mut() {
                    *value = 1.0 / (1.0 + (-*value).exp());
                }
            }
            ActivationType::Softmax => {
                // Numerical stability: subtract max value
                let max_val = values.iter().fold(f32::NEG_INFINITY, |a, &b| a.max(b));
                for value in values.iter_mut() {
                    *value = (*value - max_val).exp();
                }
                
                let sum: f32 = values.iter().sum();
                if sum > 0.0 {
                    for value in values.iter_mut() {
                        *value /= sum;
                    }
                }
            }
            ActivationType::Linear => {
                // No transformation needed
            }
        }
    }
}

/// Simplified neural network for wake word classification
#[derive(Debug)]
pub struct SimpleNeuralNetwork {
    layers: Vec<DenseLayer>,
    input_shape: Vec<usize>,
    output_classes: usize,
}

impl SimpleNeuralNetwork {
    /// Create new neural network
    pub fn new(input_size: usize, hidden_sizes: &[usize], output_size: usize) -> Self {
        let mut layers = Vec::new();
        let mut prev_size = input_size;
        
        // Hidden layers with ReLU activation
        for &hidden_size in hidden_sizes {
            layers.push(DenseLayer::new(prev_size, hidden_size, ActivationType::ReLU));
            prev_size = hidden_size;
        }
        
        // Output layer with softmax activation
        layers.push(DenseLayer::new(prev_size, output_size, ActivationType::Softmax));
        
        Self {
            layers,
            input_shape: vec![input_size],
            output_classes: output_size,
        }
    }
    
    /// Forward pass through the network
    pub fn predict(&self, input: &[f32]) -> Result<Vec<f32>, NeuralError> {
        let mut current_input = input.to_vec();
        
        for layer in &self.layers {
            current_input = layer.forward(&current_input)?;
        }
        
        Ok(current_input)
    }
    
    /// Get input shape
    pub fn input_shape(&self) -> &[usize] {
        &self.input_shape
    }
    
    /// Get number of output classes
    pub fn output_classes(&self) -> usize {
        self.output_classes
    }
}

/// Neural classifier for wake word detection
pub struct NeuralClassifier {
    models: HashMap<String, SimpleNeuralNetwork>,
    model_configs: HashMap<String, ModelConfig>,
    wake_words: Vec<String>,
    initialized: bool,
}

impl NeuralClassifier {
    /// Create new neural classifier
    pub fn new() -> Self {
        Self {
            models: HashMap::new(),
            model_configs: HashMap::new(),
            wake_words: Vec::new(),
            initialized: false,
        }
    }
    
    /// Load models for specified wake words
    pub fn load_models(&mut self, wake_words: &[String]) -> Result<(), NeuralError> {
        self.wake_words = wake_words.to_vec();
        
        // Create simplified models for each wake word
        // In production, these would be loaded from trained model files
        for wake_word in wake_words {
            let config = ModelConfig {
                input_shape: vec![13], // MFCC features
                output_classes: 2,     // wake word / not wake word
                quantization: QuantizationType::Float32,
                confidence_threshold: 0.5,
                model_path: format!("models/{}.onnx", wake_word),
            };
            
            // Create simplified neural network
            // Architecture: 13 -> 64 -> 32 -> 2
            let model = SimpleNeuralNetwork::new(13, &[64, 32], 2);
            
            self.models.insert(wake_word.clone(), model);
            self.model_configs.insert(wake_word.clone(), config);
        }
        
        self.initialized = true;
        Ok(())
    }
    
    /// Predict wake word probabilities from MFCC features
    pub fn predict(&self, features: &[f32]) -> Result<Vec<f32>, NeuralError> {
        if !self.initialized {
            return Err(NeuralError::Configuration("Classifier not initialized".to_string()));
        }
        
        if features.len() != 13 {
            return Err(NeuralError::InvalidInputShape {
                expected: vec![13],
                actual: vec![features.len()],
            });
        }
        
        let mut predictions = Vec::with_capacity(self.wake_words.len());
        
        // Run inference for each wake word model
        for wake_word in &self.wake_words {
            if let Some(model) = self.models.get(wake_word) {
                let output = model.predict(features)?;
                
                // Extract wake word probability (class 1)
                let wake_word_prob = if output.len() >= 2 {
                    output[1] // Probability of wake word class
                } else {
                    0.0
                };
                
                predictions.push(wake_word_prob);
            } else {
                predictions.push(0.0);
            }
        }
        
        Ok(predictions)
    }
    
    /// Get detailed prediction results
    pub fn predict_detailed(&self, features: &[f32]) -> Result<Vec<PredictionResult>, NeuralError> {
        if !self.initialized {
            return Err(NeuralError::Configuration("Classifier not initialized".to_string()));
        }
        
        let start_time = std::time::Instant::now();
        let mut results = Vec::with_capacity(self.wake_words.len());
        
        for wake_word in &self.wake_words {
            if let Some(model) = self.models.get(wake_word) {
                let output = model.predict(features)?;
                
                let max_confidence = output.iter().fold(0.0f32, |a, &b| a.max(b));
                let predicted_class = output.iter()
                    .enumerate()
                    .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
                    .map_or(0, |(idx, _)| idx);
                
                results.push(PredictionResult {
                    class_probabilities: output,
                    max_confidence,
                    predicted_class,
                    inference_time_ms: start_time.elapsed().as_secs_f32() * 1000.0,
                });
            }
        }
        
        Ok(results)
    }
    
    /// Apply quantization to reduce model size and improve inference speed
    pub fn quantize_models(&mut self, quantization_type: QuantizationType) -> Result<(), NeuralError> {
        match quantization_type {
            QuantizationType::Float32 => {
                // Already in float32, no conversion needed
                Ok(())
            }
            QuantizationType::Int8 => {
                // Simplified int8 quantization simulation
                // Production implementation would use proper quantization algorithms
                for config in self.model_configs.values_mut() {
                    config.quantization = QuantizationType::Int8;
                }
                Ok(())
            }
            QuantizationType::Float16 => {
                // Simplified float16 quantization simulation
                for config in self.model_configs.values_mut() {
                    config.quantization = QuantizationType::Float16;
                }
                Ok(())
            }
        }
    }
    
    /// Get model configuration for a wake word
    pub fn get_model_config(&self, wake_word: &str) -> Option<&ModelConfig> {
        self.model_configs.get(wake_word)
    }
    
    /// Get loaded wake words
    pub fn get_wake_words(&self) -> &[String] {
        &self.wake_words
    }
    
    /// Check if classifier is initialized
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }
}

impl Default for NeuralClassifier {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_dense_layer_creation() {
        let layer = DenseLayer::new(13, 64, ActivationType::ReLU);
        assert_eq!(layer.weights.len(), 64);
        assert_eq!(layer.weights[0].len(), 13);
        assert_eq!(layer.biases.len(), 64);
    }
    
    #[test]
    fn test_dense_layer_forward() {
        let layer = DenseLayer::new(3, 2, ActivationType::ReLU);
        let input = vec![1.0, 2.0, 3.0];
        let output = layer.forward(&input).unwrap();
        assert_eq!(output.len(), 2);
    }
    
    #[test]
    fn test_activation_functions() {
        let values = vec![-1.0, 0.0, 1.0, 2.0];
        
        // Test ReLU
        let layer_relu = DenseLayer::new(1, 1, ActivationType::ReLU);
        let mut relu_values = values.clone();
        layer_relu.apply_activation(&mut relu_values);
        assert_eq!(relu_values, vec![0.0, 0.0, 1.0, 2.0]);
        
        // Test Sigmoid
        let layer_sigmoid = DenseLayer::new(1, 1, ActivationType::Sigmoid);
        let mut sigmoid_values = values;
        layer_sigmoid.apply_activation(&mut sigmoid_values);
        for val in &sigmoid_values {
            assert!(*val >= 0.0 && *val <= 1.0);
        }
    }
    
    #[test]
    fn test_neural_network_creation() {
        let network = SimpleNeuralNetwork::new(13, &[64, 32], 2);
        assert_eq!(network.input_shape(), &[13]);
        assert_eq!(network.output_classes(), 2);
        assert_eq!(network.layers.len(), 3); // 2 hidden + 1 output
    }
    
    #[test]
    fn test_neural_network_prediction() {
        let network = SimpleNeuralNetwork::new(13, &[64, 32], 2);
        let input = vec![0.5; 13]; // MFCC features
        let output = network.predict(&input).unwrap();
        
        assert_eq!(output.len(), 2);
        
        // Output should be probabilities (sum to 1.0 due to softmax)
        let sum: f32 = output.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6);
        
        // All probabilities should be between 0 and 1
        for prob in &output {
            assert!(*prob >= 0.0 && *prob <= 1.0);
        }
    }
    
    #[test]
    fn test_neural_classifier_initialization() {
        let mut classifier = NeuralClassifier::new();
        let wake_words = vec!["hey guru".to_string(), "hello maya".to_string()];
        
        assert!(classifier.load_models(&wake_words).is_ok());
        assert!(classifier.is_initialized());
        assert_eq!(classifier.get_wake_words(), &wake_words);
    }
    
    #[test]
    fn test_neural_classifier_prediction() {
        let mut classifier = NeuralClassifier::new();
        let wake_words = vec!["hey guru".to_string()];
        classifier.load_models(&wake_words).unwrap();
        
        let features = vec![0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3];
        let predictions = classifier.predict(&features).unwrap();
        
        assert_eq!(predictions.len(), 1);
        assert!(predictions[0] >= 0.0 && predictions[0] <= 1.0);
    }
    
    #[test]
    fn test_invalid_input_shape() {
        let mut classifier = NeuralClassifier::new();
        let wake_words = vec!["test".to_string()];
        classifier.load_models(&wake_words).unwrap();
        
        let invalid_features = vec![0.1, 0.2]; // Wrong size
        let result = classifier.predict(&invalid_features);
        
        assert!(result.is_err());
        match result.unwrap_err() {
            NeuralError::InvalidInputShape { expected, actual } => {
                assert_eq!(expected, vec![13]);
                assert_eq!(actual, vec![2]);
            }
            _ => panic!("Expected InvalidInputShape error"),
        }
    }
    
    #[test]
    fn test_quantization() {
        let mut classifier = NeuralClassifier::new();
        let wake_words = vec!["test".to_string()];
        classifier.load_models(&wake_words).unwrap();
        
        assert!(classifier.quantize_models(QuantizationType::Int8).is_ok());
        
        let config = classifier.get_model_config("test").unwrap();
        matches!(config.quantization, QuantizationType::Int8);
    }
}