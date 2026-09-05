import pandas as pd
import numpy as np
import os

print("Loading 100k mine subsidence dataset...")
# Load the model-ready CSV dataset
df = pd.read_csv("mine_subsidence_100k_model_ready.csv")

# Ensure data is sorted chronologically
df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
df = df.sort_values(by=['node_id', 'timestamp_utc'])

# Configuration based on your TimesFM settings
context_len = 512
horizon_len = 128 # Must match your max_horizon=128 in app.py

X, y = [], []

# We process each node independently so we don't mix time-series from different sensors
nodes = df['node_id'].unique()
print(f"Processing data across {len(nodes)} sensor nodes...")

for node in nodes:
    node_data = df[df['node_id'] == node]
    values = node_data['relative_displacement_mm'].values
    
    # Create overlapping context-horizon sliding windows
    for i in range(len(values) - context_len - horizon_len):
        X.append(values[i : i + context_len])
        y.append(values[i + context_len : i + context_len + horizon_len])

X = np.array(X, dtype=np.float32)
y = np.array(y, dtype=np.float32)

print(f"Extraction complete. Generated {len(X)} training sequences.")

# Save the arrays to the backend directory
os.makedirs("backend", exist_ok=True)
np.save("backend/X_train.npy", X)
np.save("backend/y_train.npy", y)

print("Saved X_train.npy and y_train.npy successfully.")