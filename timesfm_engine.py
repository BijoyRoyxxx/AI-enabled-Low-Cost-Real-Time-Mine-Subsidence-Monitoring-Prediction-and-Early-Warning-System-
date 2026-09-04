import torch
import pandas as pd
import numpy as np
import streamlit as st
import timesfm
import timesfm.timesfm_2p5.timesfm_2p5_torch as timesfm_2p5_torch

@st.cache_resource(show_spinner=False)
def load_timesfm_engine():
    # Optimize matrix multiplication for modern hardware
    torch.set_float32_matmul_precision("high")
    
    # Load the open-source 2.5 PyTorch model
    model = timesfm_2p5_torch.TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch"
    )
    
    # Compile the configuration for zero-shot forecasting
    model.compile(
        timesfm.ForecastConfig(
            max_context=1024,
            max_horizon=256,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=True, # Subsidence cannot be negative
            fix_quantile_crossing=True, # Keeps confidence bands mathematically stable
        )
    )
    return model

def get_ai_forecast(primary_data, horizon_steps=48):
    """
    Takes the raw telemetry dataframe for a specific node, passes it through 
    the TimesFM LLM, and returns the contextual arrays needed for plotting.
    """
    timesfm_model = load_timesfm_engine()
    context_data = primary_data['displacement_mm'].values.astype(np.float32)
    
    # Generate the forecast
    point_forecast, quantile_forecast = timesfm_model.forecast(
        horizon=horizon_steps, 
        inputs=[context_data]
    )
    
    # Extract median forecast and the 10th/90th percentile boundary limits
    forecast_median = point_forecast[0] 
    q10_bounds = quantile_forecast[0, :, 1]
    q90_bounds = quantile_forecast[0, :, 9]

    # Generate future timestamps for the X-axis
    future_timestamps = pd.date_range(
        start=primary_data['timestamp'].iloc[-1], 
        periods=horizon_steps + 1, 
        freq='10min'
    )[1:]
    
    return context_data, forecast_median, q10_bounds, q90_bounds, future_timestamps