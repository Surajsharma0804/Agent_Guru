"""
Basic tests for the main training script (train.py).

This test validates that the training script can be imported and its
core functions work correctly.
"""

import os
import sys
import tempfile
import shutil
import pytest
import json

# Import the training script
import train


def test_parse_arguments_help():
    """Test that argument parsing works with help flag."""
    # This would normally exit, so we just verify the module imports
    assert hasattr(train, 'parse_arguments')
    assert hasattr(train, 'main')


def test_setup_logging():
    """Test logging setup function."""
    import logging
    
    with tempfile.TemporaryDirectory() as temp_dir:
        train.setup_logging(temp_dir, log_level="INFO")
        
        # Verify log directory was created
        log_dir = os.path.join(temp_dir, "logs")
        assert os.path.exists(log_dir)
        
        # Verify log file was created
        log_files = os.listdir(log_dir)
        assert len(log_files) > 0
        assert any(f.startswith("training_") and f.endswith(".log") for f in log_files)
        
        # Close all logging handlers to release file locks (Windows issue)
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)


def test_generate_training_report():
    """Test training report generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock preprocessing result
        from guru_vision.training.preprocess import PreprocessResult
        
        preprocess_result = PreprocessResult(
            total_images=100,
            successful=95,
            no_face=3,
            multiple_faces=2,
            failed=0,
            identities_processed=5,
            statistics={
                "Identity1": {"total": 20, "successful": 20, "no_face": 0, "multiple_faces": 0, "failed": 0},
                "Identity2": {"total": 20, "successful": 19, "no_face": 1, "multiple_faces": 0, "failed": 0}
            }
        )
        
        # Create mock training config
        from guru_vision.training.train import TrainingConfig
        config = TrainingConfig()
        
        # Generate report
        report_path = train.generate_training_report(
            output_dir=temp_dir,
            preprocess_result=preprocess_result,
            training_time=1234.5,
            model_path="guru_face/model/guru_face_model.pth",
            onnx_path="guru_face/model/guru_face_model.onnx",
            validation_passed=True,
            config=config
        )
        
        # Verify report was created
        assert os.path.exists(report_path)
        
        # Verify report content
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert "timestamp" in report
        assert "training_configuration" in report
        assert "preprocessing" in report
        assert "training" in report
        assert "onnx_export" in report
        
        # Verify preprocessing stats
        assert report["preprocessing"]["total_images"] == 100
        assert report["preprocessing"]["successful"] == 95
        assert report["preprocessing"]["identities_processed"] == 5
        
        # Verify training stats
        assert report["training"]["duration_seconds"] == 1234.5
        assert report["training"]["model_path"] == "guru_face/model/guru_face_model.pth"
        
        # Verify ONNX export stats
        assert report["onnx_export"]["performed"] is True
        assert report["onnx_export"]["validation_passed"] is True


def test_load_config_file_json():
    """Test loading configuration from JSON file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "config.json")
        
        # Create test config
        test_config = {
            "batch_size": 64,
            "learning_rate": 0.05,
            "num_epochs": 30
        }
        
        with open(config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Load config
        loaded_config = train.load_config_file(config_path)
        
        assert loaded_config["batch_size"] == 64
        assert loaded_config["learning_rate"] == 0.05
        assert loaded_config["num_epochs"] == 30


def test_load_config_file_yaml():
    """Test loading configuration from YAML file."""
    pytest.importorskip("yaml")  # Skip if PyYAML not installed
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "config.yaml")
        
        # Create test config
        config_content = """
batch_size: 64
learning_rate: 0.05
num_epochs: 30
"""
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Load config
        loaded_config = train.load_config_file(config_path)
        
        assert loaded_config["batch_size"] == 64
        assert loaded_config["learning_rate"] == 0.05
        assert loaded_config["num_epochs"] == 30


def test_main_missing_arguments():
    """Test that main function requires dataset and output arguments."""
    # Save original argv
    original_argv = sys.argv
    
    try:
        # Test with missing arguments
        sys.argv = ["train.py"]
        
        with pytest.raises(SystemExit):
            train.parse_arguments()
    
    finally:
        # Restore original argv
        sys.argv = original_argv


def test_script_imports():
    """Test that all required modules can be imported."""
    # Verify all required imports work
    assert hasattr(train, 'preprocess_dataset')
    assert hasattr(train, 'validate_dataset_structure')
    assert hasattr(train, 'check_minimum_images')
    assert hasattr(train, 'train_arcface_model')
    assert hasattr(train, 'TrainingConfig')
    assert hasattr(train, 'export_to_onnx')
    assert hasattr(train, 'validate_onnx_pytorch_equivalence')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
