import sys
import os
import zipfile
import io

# PyInstaller runtime fix
if getattr(sys, 'frozen', False):
    __import__('pkg_resources').declare_namespace('streamlit')
    sys.path.append(os.path.join(sys._MEIPASS, 'streamlit'))

import streamlit as st
import os
from pathlib import Path
import tempfile
import pandas as pd
from metadata import parse_spreadsheet, TrackMetadata
from embed import embed_metadata

# Initialize session state for WAV files list
if 'wav_files' not in st.session_state:
    st.session_state.wav_files = []

st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .main .block-container {
        max-width: 100%;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
    <h1 style='text-align: center; font-size: 48px;'>
        <strong>WAV EMBEDDER</strong>
    </h1>
""", unsafe_allow_html=True)

# Data file uploader for metadata (optional)
st.subheader("Upload Data File")
data_file = st.file_uploader("Upload Excel or CSV file", type=["xlsx", "csv"], key="data_uploader")

# Drag and drop audio
uploaded_files = st.file_uploader("Upload WAV files directly", type=["wav"], accept_multiple_files=True)

# Folder path input for WAV files
folder_path = st.text_input("Enter folder path containing WAV files", value="")



def get_wav_files_from_folder(folder):
    """Recursively gathers all WAV files from a folder and returns a list of dictionaries."""
    wav_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith('.wav'):
                wav_files.append({
                    "File Path": os.path.join(root, file),
                    "Uploaded Audio": file,  # used for display and matching metadata
                    "Filename From Data": "",
                    "Track Title": "",
                    "Source Program": "",
                    "BPM": "",
                    "Key": "",
                    "Composers": "",
                    "Publishers": ""
                })
    return sorted(wav_files, key=lambda x: x["Uploaded Audio"])

# When a valid folder is provided, update the session state.
# Process files from folder path
if folder_path and os.path.isdir(folder_path):
    st.session_state.wav_files = get_wav_files_from_folder(folder_path)

# Process uploaded files
if uploaded_files:
    # Create a temporary directory for uploaded files
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = tempfile.mkdtemp()

    # Process uploaded files
    for uploaded_file in uploaded_files:
        # Save file to temp directory
        temp_file_path = os.path.join(st.session_state.temp_dir, uploaded_file.name)
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Add to session state if not already there
        file_exists = any(file_info["File Path"] == temp_file_path for file_info in st.session_state.wav_files)
        if not file_exists:
            st.session_state.wav_files.append({
                "File Path": temp_file_path,
                "Uploaded Audio": uploaded_file.name,
                "Filename From Data": "",
                "Track Title": "",
                "Source Program": "",
                "BPM": "",
                "Key": "",
                "Composers": "",
                "Publishers": ""
            })

# Process metadata if data file is uploaded and we have WAV files.
if data_file is not None and st.session_state.wav_files:
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(data_file.name)[1], delete=False) as tmp:
            tmp.write(data_file.getvalue())
            tmp_path = tmp.name

        metadata_list = parse_spreadsheet(tmp_path)

        updated_files = []
        for file_info in st.session_state.wav_files:
            new_entry = file_info.copy()
            audio_filename = file_info["Uploaded Audio"].lower()

            # Reset metadata fields
            new_entry.update({
                "Track Title": "",
                "Source Program": "",
                "BPM": "",
                "Key": "",
                "Composers": "",
                "Publishers": ""
            })

            # Find metadata by pattern
            for m in metadata_list:
                pattern = f"{m.track_title.lower()}_"
                if pattern in audio_filename:
                    new_entry.update({
                        "Track Title": m.track_title,
                        "Source Program": m.source_program,
                        "BPM": m.bpm,
                        "Key": m.key,
                        "Composers": ", ".join(m.writers),
                        "Publishers": ", ".join(m.publishers)
                    })
                    break

            # Check for filename match
            for m in metadata_list:
                if m.filename_from_data.lower() in audio_filename:
                    new_entry["Filename From Data"] = m.filename_from_data
                    break

            updated_files.append(new_entry)
        st.session_state.wav_files = updated_files

    except Exception as e:
        st.error(f"Error parsing data file: {str(e)}")
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# Display table with metadata for editing.
if st.session_state.wav_files:
    st.subheader("Metadata")
    # Sort the files by Track Title
    st.session_state.wav_files = sorted(st.session_state.wav_files, key=lambda x: x["Track Title"].lower() if x["Track Title"] else "zzzzz")

    df = pd.DataFrame(st.session_state.wav_files)
    df.insert(0, "No.", range(1, len(df) + 1))

    # Create editable DataFrame with dynamic height and row highlighting
    edited_df = st.data_editor(
        df,
        key="wav_editor",
        use_container_width=True,
        height=35 * len(df) + 40,  # Dynamic height based on row count
        num_rows="dynamic",
        column_config={
            "_index": None,  # Hide index
            "No.": None  # Hide number column header
        }
    )

    # Update session state with edited data
    if not edited_df.equals(df):
        updated_data = edited_df.drop(columns=['No.']).to_dict('records')
        st.session_state.wav_files = updated_data


    # JavaScript for dynamic row highlighting
    st.components.v1.html(f"""
    <script>
    const rows = parent.document.querySelectorAll('[data-testid="stDataFrame"] tbody tr');
    rows.forEach(row => {{
        const filename = row.children[2].textContent.trim();
        const metadataCells = Array.from(row.children).slice(3, 9);
        const missingFields = metadataCells.some(td => td.textContent.trim() === '');

        if (missingFields) {{
            row.style.backgroundColor = '#fff3cd';  # Light yellow highlight
        }}
    }});
    </script>
    """, height=0, width=0)

# Update the CSS to handle highlighting
st.markdown("""
    <style>
    .main .block-container {
        max-width: 100%;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    [data-testid="stDataFrame"] tr:hover {{
        background-color: #f5f5f5;
    }}
    </style>
""", unsafe_allow_html=True)

# Dummy File Wrapper to simulate uploaded file behavior.
class FileWrapper:
    def __init__(self, file_path):
        self.file_path = file_path
        with open(file_path, "rb") as f:
            self.data = f.read()
    def getbuffer(self):
        return self.data

# Action buttons.
col1, col2 = st.columns(2)
with col1:
    embed_btn = st.button("EMBED FILES", type="secondary", key="embed_files_btn")


# Process files: Overwrite each file in place.
if embed_btn:
    if not st.session_state.wav_files:
        st.warning("No WAV files to process.")
    else:
        with st.spinner("Embedding metadata..."):
            errors = []
            for file_info in st.session_state.wav_files:
                original_path = file_info["File Path"]
                file_wrapper = FileWrapper(original_path)
                try:
                    # Process file using embed_metadata.
                    final_path = embed_metadata(
                        uploaded_file=file_wrapper,
                        metadata_dict={k: file_info[k] for k in ["Track Title", "Source Program", "BPM", "Key", "Composers", "Publishers"]},
                        output_filename=os.path.basename(original_path)
                    )
                    # Overwrite original file with processed data.
                    with open(final_path, "rb") as f_final:
                        processed_data = f_final.read()
                    with open(original_path, "wb") as f_original:
                        f_original.write(processed_data)
                    os.unlink(final_path)
                except Exception as e:
                    errors.append(f"{original_path}: {str(e)}")
            if errors:
                st.error("Errors occurred during processing:")
                for error in errors:
                    st.write(error)
            else:
                st.success("All WAV files have been processed and overwritten.")
                # Add this line to set the flag
                st.session_state.embedding_completed = True

if uploaded_files and st.session_state.get('embedding_completed', False):
    # Create a container for the download section
    download_container = st.container()

    with download_container:
        with st.spinner("Creating download package..."):
            # Create a zip file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                total_size = 0
                for file_info in st.session_state.wav_files:
                    file_path = file_info["File Path"]
                    filename = os.path.basename(file_path)
                    # Get file size for reporting
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    zip_file.write(file_path, filename)

            zip_buffer.seek(0)

            # Show success message with file size info
            st.success(
                f"✅ Download package ready! Contains {len(st.session_state.wav_files)} files ({total_size / 1024 / 1024:.1f} MB)")

        # Create download button with some styling
        st.markdown("""
            <style>
            div[data-testid="stDownloadButton"] button {
                background-color: #4CAF50 !important;
                color: white !important;
                font-weight: bold !important;
                padding: 0.5rem 1rem !important;
                font-size: 1.1rem !important;
            }
            </style>
        """, unsafe_allow_html=True)

        st.download_button(
            label="⬇️ DOWNLOAD PROCESSED FILES",
            data=zip_buffer,
            file_name="processed_wav_files.zip",
            mime="application/zip",
            type="primary"
        )