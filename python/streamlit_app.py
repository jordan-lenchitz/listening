import streamlit as st
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
import ssqueezepy
from affordance_field import AffordanceField
import tempfile
import os
import matplotlib
matplotlib.use('Agg')

st.set_page_config(page_title="listening dissertation demo", layout="wide")

@st.cache_data
def load_audio_internal(file_bytes, file_name):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name
    try:
        y, sr = librosa.load(tmp_path, sr=22050)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return y, sr

@st.cache_data
def process_audio_full(file_bytes, file_name):
    y, sr = load_audio_internal(file_bytes, file_name)
    if y is None or len(y) == 0:
        return None

    n_fft = 2048
    hop_length = 512
    
    # STFT - use float32/complex64 for memory efficiency
    stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length, dtype=np.complex64)
    mag = np.abs(stft).astype(np.float32)
    S_db = librosa.amplitude_to_db(mag, ref=np.max).astype(np.float32)
    
    # SSQ - limit to 10s to avoid OOM
    max_len_ssq = 10 * sr
    y_ssq = y[:max_len_ssq]
    Tx, _, _, _ = ssqueezepy.ssq_stft(y_ssq, n_fft=n_fft, hop_len=hop_length)
    Tx_mag = np.abs(Tx).astype(np.float32)
    duration_ssq = len(y_ssq) / sr
    
    # Cepstrogram
    log_S = np.log(mag + 1e-12)
    cepstrogram = np.fft.ifft(log_S, axis=0).real
    cepstrogram_display = cepstrogram[:128, :].astype(np.float32)
    
    # Affordance Field
    af = AffordanceField(sample_rate=sr, frame_length=n_fft, hop_length=hop_length)
    af_results = af.compute(y, stft=stft)
    
    return {
        "y": y,
        "sr": sr,
        "S_db": S_db,
        "Tx_mag": Tx_mag,
        "duration_ssq": duration_ssq,
        "cepstrogram_display": cepstrogram_display,
        "field": af_results["field"],
        "times": af_results["times"],
        "freqs": af_results["frequencies"],
        "n_fft": n_fft,
        "hop_length": hop_length
    }

st.title("listening affordance field and spectral analysis")

# sidebar
st.sidebar.header("settings")
cmap_option = st.sidebar.selectbox(
    "affordance field color map",
    ['viridis', 'plasma', 'inferno', 'magma', 'cividis'],
    index=0
)

# file uploader
uploaded_file = st.file_uploader("upload an audio file mp3 wav etc", type=["mp3", "wav", "m4a", "flac"])

if uploaded_file is not None:
    st.write(f"file {uploaded_file.name} detected starting processing")
    try:
        file_bytes = uploaded_file.getvalue()
        
        with st.spinner("processing audio..."):
            results = process_audio_full(file_bytes, uploaded_file.name)
            if results is None:
                st.error("failed to process audio")
                st.stop()

        # extract results to local variables
        y = results["y"]
        sr = results["sr"]
        S_db = results["S_db"]
        Tx_mag = results["Tx_mag"]
        duration_ssq = results["duration_ssq"]
        cepstrogram_display = results["cepstrogram_display"]
        field = results["field"]
        times = results["times"]
        freqs = results["freqs"]
        n_fft = results["n_fft"]
        hop_length = results["hop_length"]

        # layout: reference plots
        st.header("reference spectral analysis")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("spectrogram")
            fig_spec, ax_spec = plt.subplots(figsize=(8, 5))
            # Use imshow for efficiency
            duration = len(y) / sr
            img = ax_spec.imshow(
                S_db, 
                aspect='auto', 
                origin='lower', 
                cmap='magma',
                extent=[0, duration, 0, sr/2],
                vmin=-80, vmax=0
            )
            ax_spec.set_ylim([0, 8000])
            ax_spec.set_xlabel("time s")
            ax_spec.set_ylabel("freq hz")
            fig_spec.colorbar(img, ax=ax_spec, format="%+2.f db")
            st.pyplot(fig_spec)
            plt.close(fig_spec)

        with col2:
            st.subheader("synchrosqueezed ssq")
            fig_ssq, ax_ssq = plt.subplots(figsize=(8, 5))
            img_ssq = ax_ssq.imshow(
                Tx_mag, 
                aspect='auto', 
                origin='lower', 
                cmap='magma', 
                extent=[0, duration_ssq, 0, sr/2]
            )
            ax_ssq.set_ylim([0, 8000])
            ax_ssq.set_xlabel("time s")
            ax_ssq.set_ylabel("freq hz")
            fig_ssq.colorbar(img_ssq, ax=ax_ssq)
            st.pyplot(fig_ssq)
            plt.close(fig_ssq)

        with col3:
            st.subheader("cepstrogram")
            fig_cep, ax_cep = plt.subplots(figsize=(8, 5))
            img_cep = ax_cep.imshow(
                cepstrogram_display, 
                aspect='auto', 
                origin='lower', 
                cmap='viridis'
            )
            ax_cep.set_xlabel("time frames")
            ax_cep.set_ylabel("quefrency bins")
            fig_cep.colorbar(img_cep, ax=ax_cep)
            st.pyplot(fig_cep)
            plt.close(fig_cep)

        # affordance field
        st.header(f"affordance field colormap {cmap_option}")
        fig_af, ax_af = plt.subplots(figsize=(12, 6))
        im_af = ax_af.imshow(
            field, 
            aspect='auto', 
            origin='lower', 
            cmap=cmap_option,
            extent=[times[0], times[-1], freqs[0], freqs[-1]]
        )
        ax_af.set_ylim([60, 4000])
        ax_af.set_title("spectral affordance field a t f")
        ax_af.set_xlabel("time s")
        ax_af.set_ylabel("freq hz")
        fig_af.colorbar(im_af, ax=ax_af)
        st.pyplot(fig_af)
        plt.close(fig_af)

        # audio player
        st.audio(file_bytes, format=f"audio/{os.path.splitext(uploaded_file.name)[1][1:]}")

    except Exception as e:
        st.error(f"error during processing: {str(e).lower()}")
        import traceback
        st.code(traceback.format_exc())

else:
    st.info("welcome please upload an audio file to begin the spectral analysis the processing will start immediately after the upload is complete")
    
    st.markdown("""
    ### about this tool
    this dashboard provides a comprehensive look at audio through multiple spectral lenses
    - **spectrogram** standard stft magnitude in db
    - **synchrosqueezed ssq** a reassigned time frequency representation that sharpens spectral components
    - **cepstrogram** reveal periodicities in the spectrum useful for pitch and timbre analysis
    - **affordance field** a composite feature field representing listening affordances availability persistence continuity change and coherence
    """)
