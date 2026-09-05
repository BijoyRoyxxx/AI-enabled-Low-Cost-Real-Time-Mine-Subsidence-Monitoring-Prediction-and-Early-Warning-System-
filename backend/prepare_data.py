import sqlite3
import pandas as pd
import numpy as np

# 1. Connect to your local database
conn = sqlite3.connect("geoshield.db")

# 2. Extract telemetry for your critical node (e.g., N13)
# We need displacement_mm ordered chronologically
query = """
    SELECT timestamp, displacement_mm 
    FROM telemetry_logs 
    WHERE node_id = 'N13' 
    ORDER BY timestamp ASC
"""
df = pd.read_sql_query(query, conn)
conn.close()

# 3. Create overlapping windows for training
# TimesFM uses a context window to predict a horizon
context_len = 512  # How many past 5s readings to look at
horizon_len = 16   # How many future readings to predict (e.g., 16 steps = 8 hours at 30m intervals)

X, y = [], []
values = df['displacement_mm'].values

for i in range(len(values) - context_len - horizon_len):
    X.append(values[i : i + context_len])
    y.append(values[i + context_len : i + context_len + horizon_len])

X = np.array(X)
y = np.array(y)

print(f"Prepared {len(X)} training sequences.")
np.save("backend/X_train.npy", X)
np.save("backend/y_train.npy", y)