#updated 06/16, uses header names provided by file
import os
import pandas as pd
import json
import tkinter as tk
from tkinter import filedialog

# GUI folder picker
root = tk.Tk()
root.withdraw()  # Hide the root window

folder_path = filedialog.askdirectory(title="Select Folder with .txt Files")

if not folder_path:
    raise ValueError("No folder selected. Exiting script.")
print(folder_path)

DataFrame = {}
for filename in os.listdir(folder_path):
    if filename.endswith(".txt"):
        full_path = os.path.join(folder_path, filename)

        data = []
        with open(full_path, "r") as file:
            for line in file:
                clean = line.strip().strip('"').replace('""','"')
                try:
                    parsed = json.loads(clean)
                    data.append(parsed)
                except json.JSONDecodeError:
                    print(f"Error decoding line in {filename}")

        df = pd.json_normalize(data)

        # Extract and rename
        # input_df = pd.DataFrame(df['input'].tolist()).add_prefix('input')
        # output_df = pd.DataFrame(df['output'].tolist()).add_prefix('output')
        # full_df = pd.concat([df['sn', 'time']], axis=1)
        full_df = df
        df_name = filename.replace('.txt', '')  # e.g., '10-27-51__algorithm'
        DataFrame[df_name] = full_df  # Store in dictionary

        # Save to CSV in the same or another folder
        output_filename = filename.replace('.txt', '_parsed.csv')
        full_df.to_csv(os.path.join(folder_path, output_filename), index=False)
        print(f"Saved: {output_filename}")

root.quit()  # Close the tkinter root window
