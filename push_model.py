from peft import PeftModel
from transformers import TimesFm2_5ModelForPrediction

# Load the base model and your local GPU-trained weights
base_model = TimesFm2_5ModelForPrediction.from_pretrained("google/timesfm-2.5-200m-transformers")
model = PeftModel.from_pretrained(base_model, "backend/models/timesfm-mine-finetuned")

# CRITICAL: Replace 'your-username' with your actual Hugging Face username
model.push_to_hub("your-username/timesfm-2.5-mine-subsidence-lora")