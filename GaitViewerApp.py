import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import datetime

# --- Utility Functions ---
def seconds_to_hms(seconds):
    return str(datetime.timedelta(seconds=seconds))

def compress_repeats_with_index(lst):
    if not lst:
        return [], []
    compressed, indices = [lst[0]], [0]
    for i in range(1, len(lst)):
        if lst[i] != compressed[-1]:
            compressed.append(lst[i])
            indices.append(i)
    return compressed, indices

def find_sequence_with_original_indices(column, sequence):
    matches = []
    compressed, indices = compress_repeats_with_index(column)
    for i in range(len(compressed) - len(sequence) + 1):
        if compressed[i:i + len(sequence)] == sequence:
            start = indices[i]
            j = indices[i + len(sequence) - 1]
            while j + 1 < len(column) and column[j + 1] == sequence[-1]:
                j += 1
            matches.append((start, j))
    return matches

def find_gait_transitions(column):
    GC_013 = find_sequence_with_original_indices(column, [0, 1, 3])
    GC_0123 = find_sequence_with_original_indices(column, [0, 1, 2, 3])
    matches = sorted(GC_013 + GC_0123, key=lambda x: x[0])

    segments = []
    prev_end = -1
    for start, end in matches:
        if prev_end + 1 < start:
            segments.append((prev_end + 1, start - 1, 'NonGait'))
        segments.append((start, end, 'Gait'))
        prev_end = end
    if prev_end + 1 < len(column):
        segments.append((prev_end + 1, len(column) - 1, 'NonGait'))
    return segments

def label_phases_within_cycles(column, gait_cycles):
    labels = ['Other'] * len(column)
    for start, end in gait_cycles:
        for i in range(start, end + 1):
            if column[i] in [0, 3]:
                labels[i] = 'Stance'
            elif column[i] in [1, 2]:
                labels[i] = 'Swing'
    return labels

def label_gait_and_nongait(column):
    labels = ['Other'] * len(column)
    segments = find_gait_transitions(column)
    for start, end, label in segments:
        for i in range(start, end + 1):
            labels[i] = label
    return labels

def label_gait_phases(df):
    phase_col = df['phase'].tolist()
    gait_segments = find_gait_transitions(phase_col)
    gait_cycles = [(s, e) for s, e, label in gait_segments if label == 'Gait']
    gait_labels = label_gait_and_nongait(phase_col)
    phase_labels = label_phases_within_cycles(phase_col, gait_cycles)
    final_labels = [p if g == 'Gait' else 'NonGait' for g, p in zip(gait_labels, phase_labels)]
    return gait_cycles, gait_labels, phase_labels, final_labels


# Main App
def main():
    st.title("📈 Gait Analysis Viewer")
    st.markdown("Analyze knee/thigh angle phases and export gait durations.")

    uploaded_files = st.file_uploader("📤 Upload one or more `.txt` files", type="txt", accept_multiple_files=True)
    prefixes = st.text_input("🔍 Filter filenames with prefix (comma-separated)", value="10-33-13,14-02-29")
    prefixes = [p.strip() for p in prefixes.split(",") if p.strip()]

    if uploaded_files:
        process_uploaded_files(uploaded_files, prefixes)


def process_uploaded_files(uploaded_files, prefixes):
    DataFrame = {}

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        if not filename.endswith(".txt"):
            continue
        data = []
        for line in uploaded_file:
            clean = line.decode("utf-8").strip().strip('"').replace('""', '"')
            try:
                parsed = json.loads(clean)
                data.append(parsed)
            except:
                st.warning(f"Could not parse line in {filename}")
        df = pd.json_normalize(data)
        if 'input' in df and 'output' in df:
            input_df = pd.DataFrame(df['input'].tolist()).add_prefix('input')
            output_df = pd.DataFrame(df['output'].tolist()).add_prefix('output')
            full_df = pd.concat([df[['sn', 'time']], input_df, output_df], axis=1)
            full_df.rename(columns={
                'sn': 'sample_number',
                'input0': 'mode',
                'input1': 'phase',
                'input4': 'knee_angle (degree)',
                'input6': 'thigh_angle(degree)',
                'input8': 'calf_angle(degree)',
                'time': 'timestamp'
            }, inplace=True)
            DataFrame[filename.replace(".txt", "")] = full_df

    for file_name, df in DataFrame.items():
        if not any(file_name.startswith(p) for p in prefixes):
            continue

        st.subheader(f"📁 Processing File: {file_name}")
        filtered_df = df[df['mode'] == 0].reset_index(drop=True)

        if filtered_df.empty:
            st.warning(f"No Mode 0 data in {file_name}")
            continue

        filtered_df['human_time'] = filtered_df['timestamp'] - filtered_df['timestamp'].iloc[0]
        filtered_df['human_time'] = filtered_df['human_time'].apply(seconds_to_hms)

        overall_duration = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
        gait_cycles, gait_labels, phase_labels, final_labels = label_gait_phases(filtered_df)

        # Gait-only duration
        gait_only_duration = sum(filtered_df['timestamp'].iloc[end] - filtered_df['timestamp'].iloc[start]
                                 for start, end in gait_cycles)

        with st.sidebar:
            st.markdown(f"**📁 File:** `{file_name}`")
            st.markdown(f"🕒 Overall Duration: `{overall_duration:.2f}` s")
            st.markdown(f"🚶 Gait-Only Duration: `{gait_only_duration:.2f}` s")
            st.markdown(f"👣 Total Gait Cycles: `{len(gait_cycles)}`")

        # Label and add columns
        filtered_df['gait_label'] = gait_labels
        filtered_df['phase_label'] = phase_labels
        filtered_df['final_label'] = final_labels

        # Plot angles
        st.markdown("### 📊 Knee & Thigh Angle Plot")
        fig, axs = plt.subplots(2, 1, figsize=(12, 6))
        gait_df = filtered_df[filtered_df['gait_label'] == 'Gait'].reset_index(drop=True)
        axs[0].plot(gait_df['timestamp'], gait_df['knee_angle (degree)'], label="Knee Angle", color='red')
        axs[1].plot(gait_df['timestamp'], gait_df['thigh_angle(degree)'], label="Thigh Angle", color='blue')
        axs[0].set_ylabel("Knee (°)")
        axs[1].set_ylabel("Thigh (°)")
        axs[1].set_xlabel("Time (s)")
        axs[0].legend()
        axs[1].legend()
        st.pyplot(fig)

        # Segment info
        st.markdown("### 📋 Export Phase Durations")
        x_data = filtered_df['timestamp'] - filtered_df['timestamp'].iloc[0]
        labels = filtered_df['final_label'].tolist()
        segment_info = []
        start_idx = 0
        for i in range(1, len(labels)):
            if labels[i] != labels[i - 1]:
                seg_label = labels[i - 1]
                seg_start, seg_end = x_data.iloc[start_idx], x_data.iloc[i - 1]
                segment_info.append({
                    'Phase': seg_label,
                    'Start Time (s)': seg_start,
                    'End Time (s)': seg_end,
                    'Duration (s)': seg_end - seg_start
                })
                start_idx = i
        segment_info.append({
            'Phase': labels[-1],
            'Start Time (s)': x_data.iloc[start_idx],
            'End Time (s)': x_data.iloc[-1],
            'Duration (s)': x_data.iloc[-1] - x_data.iloc[start_idx]
        })
        segment_df = pd.DataFrame(segment_info)
        st.dataframe(segment_df)

        csv = segment_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download CSV", csv, f"{file_name}_durations.csv", "text/csv")

        # Duration tables
        stance_durations = segment_df[segment_df['Phase'] == 'Stance']['Duration (s)'].reset_index(drop=True)
        swing_durations = segment_df[segment_df['Phase'] == 'Swing']['Duration (s)'].reset_index(drop=True)
        max_len = max(len(stance_durations), len(swing_durations))
        stance_durations = stance_durations.reindex(range(max_len))
        swing_durations = swing_durations.reindex(range(max_len))
        stance_swing_ratio = stance_durations / swing_durations
        gait_cycle_durations = [filtered_df['timestamp'].iloc[end] - filtered_df['timestamp'].iloc[start]
                                for start, end in gait_cycles]
        gait_cycle_durations = pd.Series(gait_cycle_durations).reindex(range(max_len))

        duration_table = pd.DataFrame({
            'Stance Duration (s)': stance_durations,
            'Swing Duration (s)': swing_durations,
            'Stance:Swing Ratio': stance_swing_ratio,
            'Gait Cycle Duration (s)': gait_cycle_durations
        })

        mask = (
            (duration_table['Stance Duration (s)'] >= 0.2) &
            (duration_table['Stance Duration (s)'] <= 2) &
            (duration_table['Swing Duration (s)'] >= 0.2) &
            (duration_table['Swing Duration (s)'] <= 1.5) &
            (duration_table['Stance:Swing Ratio'] >= 0.5) &
            (duration_table['Stance:Swing Ratio'] <= 3) &
            (duration_table['Gait Cycle Duration (s)'] >= 0.5) &
            (duration_table['Gait Cycle Duration (s)'] <= 3)
        )

        filtered_duration_table = duration_table[mask].reset_index(drop=True)

        st.markdown("### ✅ Filtered Gait Durations")
        st.dataframe(filtered_duration_table)

        csv_filtered = filtered_duration_table.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Filtered Durations", csv_filtered,
                           f"{file_name}_filtered_durations.csv", "text/csv")

        csv_all = duration_table.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download All Durations", csv_all,
                           f"{file_name}_all_durations.csv", "text/csv")

        st.success(f"🚶 Valid Step Count: {len(filtered_duration_table)}")


if __name__ == "__main__":
    main()
