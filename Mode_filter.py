#================================FOR USE==================
# Mode filtering algorithm - Folder save for durations 
# Find:
# Ex: column - Mode == 5 #Protection measure or safety mode 
    # 0 - normal
    # 1 - stance lock
    # 2 - climb stairs
    # 3 - sitting
    # 4 - user defined (custom mode)
    # 5 - safety (user has fallen down)
    # 6- down stairs & down ramp
    # 7- manual lock
    # 8- backwards walking

# Index start, end instance of mode ==5
# Duration from start, end index
# Outputs: Mode_summaries


import pandas as pd
import tkinter
from tkinter import filedialog
import os
import json
import matplotlib.pyplot as plt
import numpy as np
%matplotlib inline

# GUI folder picker
tkinter.Tk().withdraw()
folder_path = filedialog.askdirectory(title="Select Folder with .txt Files")

if not folder_path:
    raise ValueError(" No folder selected. Exiting script.")
print(folder_path)

# ---- Set folder path ----
folder_path = r"C:\Users\KevWal\Downloads\20250515"

# ---- Load files ----
DataFrame = {}
for filename in os.listdir(folder_path):
    if filename.endswith(".txt"):
        full_path = os.path.join(folder_path, filename)
        data = []
        with open(full_path, "r") as file:
            for line in file:
                clean = line.strip().strip('"').replace('""', '"')
                try:
                    parsed = json.loads(clean)
                    data.append(parsed)
                except json.JSONDecodeError:
                    print(f"Error decoding line in {filename}")
        df = pd.json_normalize(data)
        if 'input' in df and 'output' in df:
            input_df = pd.DataFrame(df['input'].tolist()).add_prefix('input')
            output_df = pd.DataFrame(df['output'].tolist()).add_prefix('output')
            full_df = pd.concat([df[['sn', 'time']], input_df, output_df], axis=1)
            full_df.rename(columns={
                'sn': 'sample_number',
                'input0': 'mode',
                'input1': 'phase',
                'input2': 'flex_damp_measure',
                'input3': 'ext_damp_measure',
                'input4': 'knee_angle (degree)',
                'input5': 'knee_velocity(degree/s)',
                'input6': 'thigh_position(degree)',
                'input7': 'thigh_velocity(degree/s)',
                'input8': 'calf_position(degree)',
                'input9': 'calf_velocity(degree/s)',
                'input10': 'calf_ang_acc_smooth(degree/s²)',
                'input11': 'acc_abs_mag',
                'input12': 'acc_vertical_world',
                'input13': 'abs_knee_vel_avg(degree/s)',
                'input14': 'knee_velocity_history',
                'input15': 'reserved',
                'output0': 'motor_flex',
                'output1': 'motor_extent',
                'time': 'timestamp'
            }, inplace=True)
            df_name = filename.replace('.txt', '')
            DataFrame[df_name] = full_df


# ----  Mode filtering functions by segements ----

def find_mode_segments(mode_series, target_mode):
    segments = []  # store (start, end) index pairs
    in_segment = False  # track if you're currently in a segment
    start_idx = None  # track where a segment starts
    for i, val in enumerate(mode_series):
        # Start of a new segment
        if val == target_mode and not in_segment:
            in_segment = True
            start_idx = i
        elif val != target_mode and in_segment:
            # End of current segment
            in_segment = False
            end_idx = i - 1
            segments.append((start_idx, end_idx))
    if in_segment:
        segments.append((start_idx, len(mode_series) - 1))
    return segments

   



mode_labels = {
    0: "Normal Walk",
    1: "Stance Lock",
    2: "Stair Climb",
    3: "Sitting",
    4: "Custom",
    5: "Protection / Safety",
    6: "Downstairs / Ramp",
    7: "Manual Lock",
    8: "Backwards Walk"
}



# ---- Process each file ----

# Define the folder path to save summaries
summary_folder = os.path.join(folder_path, "mode_summaries")

# Create the folder if it doesn't exist
os.makedirs(summary_folder, exist_ok=True)

for file_name, df in DataFrame.items():
    print(f"\n📁 Processing file: {file_name}")

    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df.dropna(subset=['timestamp'], inplace=True)
    df['timestamp'] -= df['timestamp'].iloc[0]
    
    overall_duration = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
    # Convert overall duration to minutes and seconds
    overall_mins, overall_secs = divmod(overall_duration, 60)
    minutes_duration = f"{int(overall_mins)} min {int(overall_secs)} sec"

    mode_summary = []  # To store summary per mode

    for mode_value in range(9):
        segments = find_mode_segments(df['mode'], mode_value)
        mode_duration = 0.0
        
        for (start_idx, end_idx) in segments:
            seg = df.iloc[start_idx:end_idx + 1]
            segment_duration = seg['timestamp'].iloc[-1] - seg['timestamp'].iloc[0]
            mode_duration += segment_duration

        mode_summary.append({
            'Mode': mode_value,
            'Label': mode_labels[mode_value],
            'Event Count': len(segments),
            'Total Duration (s)': round(mode_duration, 2),
            '% of Total Duration': round((mode_duration / overall_duration) * 100, 2) if overall_duration > 0 else 0
        })

    # ---- Create DataFrame Summary ----
    summary_df = pd.DataFrame(mode_summary)
    print("\n📊 Summary Table:")
    print(summary_df)
    
    print(f"\n🕒 Overall Sampling Duration: {overall_duration:.2f} seconds "
          f"({minutes_duration})\n")

     # Save CSV inside the new folder
    save_path = os.path.join(summary_folder, f"{file_name}_mode_summary.csv")
    summary_df.to_csv(save_path, index=False)
    print(f"✅ Saved summary CSV for {file_name} to {save_path}")
