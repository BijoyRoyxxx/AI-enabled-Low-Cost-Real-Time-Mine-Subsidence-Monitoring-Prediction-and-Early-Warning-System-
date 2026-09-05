import numpy as np
import torch
from transformers import TimesFm2_5ModelForPrediction
from peft import LoraConfig, get_peft_model
import traceback
import gc # For Python garbage collection

# 1. Load the prepared 100k data arrays
X_train = np.load("backend/X_train.npy")
y_train = np.load("backend/y_train.npy")

# Explicitly assign your RTX 3050 Ti
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Hardware allocated: {device}")

# Clear any lingering VRAM from previous crashes
torch.cuda.empty_cache()

model = TimesFm2_5ModelForPrediction.from_pretrained("google/timesfm-2.5-200m-transformers")

config = LoraConfig(
    r=8, 
    lora_alpha=16, 
    target_modules=["q_proj", "v_proj"], 
    lora_dropout=0.1, 
    bias="none"
)
model = get_peft_model(model, config)
model = model.to(device)

optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

print("Starting GPU training on historical subsidence data...")
model.train()

# VRAM-Optimized Training Settings for 4GB GPU
batch_size = 4  # Drastically reduced from 32 to prevent OOM
epochs = 1
num_batches = 500

for epoch in range(epochs):
    epoch_loss = 0
    for i in range(num_batches): 
        start_idx = i * batch_size
        end_idx = start_idx + batch_size
        
        try:
            # Send small batches to VRAM
            past_values = torch.tensor(X_train[start_idx:end_idx], dtype=torch.float32).to(device)
            future_values = torch.tensor(y_train[start_idx:end_idx], dtype=torch.float32).to(device)
            
            optimizer.zero_grad()
            outputs = model(past_values=past_values, future_values=future_values)
            
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            
            if (i + 1) % 100 == 0:
                print(f"Epoch {epoch + 1}/{epochs} | Batch {i + 1}/{num_batches} | Loss: {loss.item():.4f}")
                
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Crash at Epoch {epoch}, Batch {i}:")
            traceback.print_exc()
            break 
            
        # Aggressive Memory Management: Free up unused VRAM frequently
        if i % 10 == 0:
            torch.cuda.empty_cache()
            gc.collect()
            
    print(f"--- Epoch {epoch + 1} Complete | Avg Loss: {epoch_loss / max(1, num_batches):.4f} ---")

model.save_pretrained("backend/models/timesfm-mine-finetuned")
print("GPU LoRA weights saved successfully.")