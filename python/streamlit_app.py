import streamlit as st
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
import ssqueezepy
from affordance_field import AffordanceField
import tempfile
import os
import time

st.set_page_config(page_title="listening dissertation demo", layout="wide")

@st.cache_data
def get_audio_duration(file_bytes, file_name):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name
    try:
        duration = librosa.get_duration(path=tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return duration

def process_audio_chunked(file_bytes, file_name, chunk_size=10.0):
    duration_total = get_audio_duration(file_bytes, file_name)
    n_chunks = int(np.ceil(duration_total / chunk_size))
    
    sr = 22050
    n_fft = 2048
    hop_length = 512
    
    af = AffordanceField(sample_rate=sr, frame_length=n_fft, hop_length=hop_length)
    
    all_results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # We'll save the file once to avoid repeated writes
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name

    try:
        for i in range(n_chunks):
            offset = i * chunk_size
            status_text.text(f"processing chunk {i+1}/{n_chunks} ({offset:.1f}s - {min(offset+chunk_size, duration_total):.1f}s)")
            
            # Load chunk
            y_chunk, _ = librosa.load(tmp_path, sr=sr, offset=offset, duration=chunk_size)
            
            if len(y_chunk) < n_fft:
                continue
                
            # STFT
            stft = librosa.stft(y_chunk, n_fft=n_fft, hop_length=hop_length, dtype=np.complex64)
            mag = np.abs(stft)
            S_db = librosa.amplitude_to_db(mag, ref=np.max).astype(np.float32)
            
            # SSQ (CPU intensive, so we definitely want this chunked)
            Tx, _, _, _ = ssqueezepy.ssq_stft(y_chunk, n_fft=n_fft, hop_len=hop_length)
            Tx_mag = np.abs(Tx).astype(np.float32)
            
            # Affordance Field
            af_results = af.compute(y_chunk, stft=stft)
            
            all_results.append({
                "offset": offset,
                "duration": len(y_chunk) / sr,
                "S_db": S_db,
                "Tx_mag": Tx_mag,
                "field": af_results["field"],
                "times": af_results["times"] + offset,
                "freqs": af_results["frequencies"]
            })
            
            progress_bar.progress((i + 1) / n_chunks)
            
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return all_results, sr

st.title("listening - spectral affordance analysis (chunked)")

# sidebar
st.sidebar.header("analysis settings")
chunk_size = st.sidebar.slider("chunk size (seconds)", 5.0, 30.0, 10.0)
cmap_option = st.sidebar.selectbox(
    "colormap",
    ['viridis', 'plasma', 'inferno', 'magma', 'turbo'],
    index=4
)

# file uploader
uploaded_file = st.file_uploader("upload audio (mp3, wav, flac)", type=["mp3", "wav", "m4a", "flac"])

if uploaded_file is not None:
    st.write(f"file: {uploaded_file.name}")
    try:
        file_bytes = uploaded_file.getvalue()
        
        results, sr = process_audio_chunked(file_bytes, uploaded_file.name, chunk_size=chunk_size)
        
        if not results:
            st.error("failed to process audio")
            st.stop()

        st.success(f"processed {len(results)} chunks")

        # Visualization
        st.header("analysis results")
        
        # Select chunk to view
        chunk_idx = st.select_slider("select chunk to visualize", options=range(len(results)), format_func=lambda x: f"chunk {x+1} ({results[x]['offset']:.1f}s)")
        
        res = results[chunk_idx]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("spectrogram (stft)")
            fig_spec, ax_spec = plt.subplots(figsize=(10, 5))
            img = ax_spec.imshow(
                res["S_db"], 
                aspect='auto', 
                origin='lower', 
                cmap='magma',
                extent=[res["offset"], res["offset"] + res["duration"], 0, sr/2],
                vmin=-80, vmax=0
            )
            ax_spec.set_ylim([0, 8000])
            ax_spec.set_xlabel("time (s)")
            ax_spec.set_ylabel("freq (hz)")
            fig_spec.colorbar(img, ax=ax_spec, format="%+2.f db")
            st.pyplot(fig_spec)
            plt.close(fig_spec)

        with col2:
            st.subheader("synchrosqueezed (ssq)")
            fig_ssq, ax_ssq = plt.subplots(figsize=(10, 5))
            img_ssq = ax_ssq.imshow(
                res["Tx_mag"], 
                aspect='auto', 
                origin='lower', 
                cmap='magma', 
                extent=[res["offset"], res["offset"] + res["duration"], 0, sr/2]
            )
            ax_ssq.set_ylim([0, 8000])
            ax_ssq.set_xlabel("time (s)")
            ax_ssq.set_ylabel("freq (hz)")
            fig_ssq.colorbar(img_ssq, ax=ax_ssq)
            st.pyplot(fig_ssq)
            plt.close(fig_ssq)

        st.subheader(f"affordance field ({cmap_option})")
        fig_af, ax_af = plt.subplots(figsize=(15, 6))
        im_af = ax_af.imshow(
            res["field"], 
            aspect='auto', 
            origin='lower', 
            cmap=cmap_option,
            extent=[res["times"][0], res["times"][-1], res["freqs"][0], res["freqs"][-1]]
        )
        ax_af.set_ylim([60, 4000])
        ax_af.set_title(f"spectral affordance field - chunk {chunk_idx+1}")
        ax_af.set_xlabel("time (s)")
        ax_af.set_ylabel("freq (hz)")
        fig_af.colorbar(im_af, ax=ax_af)
        st.pyplot(fig_af)
        plt.close(fig_af)

        # audio player
        st.audio(file_bytes, format=f"audio/{os.path.splitext(uploaded_file.name)[1][1:]}")

    except Exception as e:
        st.error(f"error: {str(e)}")

else:
    st.info("upload audio to begin analysis")
    st.markdown("""
    ### listening affordance analysis
    this tool uses chunked processing to analyze audio through:
    - **stft spectrogram**
    - **synchrosqueezing** (sharpened time-frequency)
    - **affordance field** (multi-feature listening representation)
    """)
