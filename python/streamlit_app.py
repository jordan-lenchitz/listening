import streamlit as st
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
import ssqueezepy
from affordance_field import AffordanceField
import tempfile
import os

st.set_page_config(page_title="listening dissertation demo", layout="wide")

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
    st.write("file detected starting processing")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        with st.status("processing audio this may take a minute") as status:
            st.write("loading audio")
            y, sr = librosa.load(tmp_path, sr=22050)
            
            st.write("computing spectrogram")
            n_fft = 2048
            hop_length = 512
            stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
            S_db = librosa.amplitude_to_db(np.abs(stft), ref=np.max)

            st.write("computing synchrosqueezed representation")
            # limit to 10s for the ssq part to ensure it finishes
            max_len_ssq = 10 * sr
            y_ssq = y[:max_len_ssq]
            # ssq_stft returns 4 values tx wx ssq_freqs and scales
            Tx, Wx, ssq_freqs, _ = ssqueezepy.ssq_stft(y_ssq, n_fft=n_fft, hop_len=hop_length)
            Tx_mag = np.abs(Tx)

            st.write("computing cepstrogram")
            log_S = np.log(np.abs(stft) + 1e-12)
            cepstrogram = np.fft.ifft(log_S, axis=0).real
            cepstrogram_display = cepstrogram[:128, :]

            st.write("computing affordance field")
            af = AffordanceField(sample_rate=sr, frame_length=n_fft, hop_length=hop_length)
            af_results = af.compute(y)
            field = af_results["field"]
            times = af_results["times"]
            freqs = af_results["frequencies"]
            status.update(label="processing complete", state="complete")

        # layout: reference plots
        st.header("reference spectral analysis")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("spectrogram")
            fig_spec, ax_spec = plt.subplots(figsize=(8, 5))
            img = librosa.display.specshow(S_db, x_axis='time', y_axis='linear', sr=sr, hop_length=hop_length, ax=ax_spec, cmap='magma')
            ax_spec.set_ylim([0, 8000])
            fig_spec.colorbar(img, ax=ax_spec, format="%+2.f db")
            st.pyplot(fig_spec)
            plt.close(fig_spec)

        with col2:
            st.subheader("synchrosqueezed ssq")
            fig_ssq, ax_ssq = plt.subplots(figsize=(8, 5))
            duration_ssq = len(y_ssq) / sr
            img_ssq = ax_ssq.imshow(Tx_mag, aspect='auto', origin='lower', cmap='magma', 
                                   extent=[0, duration_ssq, 0, sr/2])
            ax_ssq.set_ylim([0, 8000])
            ax_ssq.set_xlabel("time s")
            ax_ssq.set_ylabel("freq hz")
            fig_ssq.colorbar(img_ssq, ax=ax_ssq)
            st.pyplot(fig_ssq)
            plt.close(fig_ssq)

        with col3:
            st.subheader("cepstrogram")
            fig_cep, ax_cep = plt.subplots(figsize=(8, 5))
            img_cep = ax_cep.imshow(cepstrogram_display, aspect='auto', origin='lower', cmap='viridis')
            ax_cep.set_xlabel("time frames")
            ax_cep.set_ylabel("quefrency bins")
            fig_cep.colorbar(img_cep, ax=ax_cep)
            st.pyplot(fig_cep)
            plt.close(fig_cep)

        # affordance field
        st.header(f"affordance field colormap {cmap_option}")
        fig_af, ax_af = plt.subplots(figsize=(12, 6))
        im_af = ax_af.pcolormesh(times, freqs, field, shading='auto', cmap=cmap_option)
        ax_af.set_ylim([60, 4000])
        ax_af.set_title("spectral affordance field a t f")
        ax_af.set_xlabel("time s")
        ax_af.set_ylabel("freq hz")
        fig_af.colorbar(im_af, ax=ax_af)
        st.pyplot(fig_af)
        plt.close(fig_af)

        # audio player
        st.audio(uploaded_file)

    except Exception as e:
        st.error(f"error during processing {str(e).lower()}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

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
