import streamlit as st
import pandas as pd
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

# --- Main App ---

def main():
    st.title("📈 Gait Analysis Viewer (No Plotting)")
    st.markdown("Upload `.txt` files to extract and export valid gait phase durations.")

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
        gait_only_duration = sum(filtered_df['timestamp'].iloc[end] - filtered_df['timestamp'].iloc[start] for start, end in gait_cycles)

        # Assign labels
        filtered_df['gait_label'] = gait_labels
        filtered_df['phase_label'] = phase_labels
        filtered_df['final_label'] = final_labels

        # Exportable segment-level durations
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

        # Phase duration tables
        stance_durations = segment_df[segment_df['Phase'] == 'Stance']['Duration (s)'].reset_index(drop=True)
        swing_durations = segment_df[segment_df['Phase'] == 'Swing']['Duration (s)'].reset_index(drop=True)
        max_len = max(len(stance_durations), len(swing_durations))
        stance_durations = stance_durations.reindex(range(max_len))
        swing_durations = swing_durations.reindex(range(max_len))
        stance_swing_ratio = stance_durations / swing_durations
        gait_cycle_durations = [filtered_df['timestamp'].iloc[end] - filtered_df['timestamp'].iloc[start] for start, end in gait_cycles]
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
        valid_step_count = len(filtered_duration_table)

        # Sidebar summary
        with st.sidebar:
            st.markdown(f"**📁 File:** `{file_name}`")
            st.markdown(f"🕒 Overall Duration: `{overall_duration:.2f}` s")
            st.markdown(f"🚶 Gait-Only Duration: `{gait_only_duration:.2f}` s")
            st.markdown(f"🔄 Total Gait Cycles (raw): `{len(gait_cycles)}`")
            st.markdown(f"✅ Filtered Gait Cycles: `{valid_step_count}`")
            st.markdown(f"👣 Valid Step Count: `{valid_step_count}`")

        # Export section
        st.markdown("### 📋 Export Phase Durations")
        st.dataframe(segment_df)
        st.download_button("⬇️ Download Full Durations", segment_df.to_csv(index=False).encode('utf-8'), f"{file_name}_durations.csv", "text/csv")

        st.markdown("### ✅ Filtered Gait Durations")
        st.dataframe(filtered_duration_table)
        st.download_button("⬇️ Download Filtered Durations", filtered_duration_table.to_csv(index=False).encode('utf-8'), f"{file_name}_filtered_durations.csv", "text/csv")
        st.success(f"Filtered Steps: {valid_step_count}")

if __name__ == "__main__":
    main()
