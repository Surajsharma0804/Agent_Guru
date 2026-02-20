# Set CUDA environment variable
$env:CUDA_VISIBLE_DEVICES = "0"

# Run training
python Agent_Guru/reasoning/train_intent_classifier.py
