import streamlit as st
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from affordance_field import AffordanceField
import tempfile
import os
import time
from pydub import AudioSegment
import io
import base64
import json
import streamlit.components.v1 as components

st.set_page_config(page_title="listening dissertation demo", layout="wide", initial_sidebar_state="collapsed")

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

@st.cache_data
def get_chunk_audio(file_bytes, file_name, offset, duration):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name
    try:
        audio = AudioSegment.from_file(tmp_path)
        start_ms = offset * 1000
        end_ms = (offset + duration) * 1000
        chunk = audio[start_ms:end_ms]
        
        buffer = io.BytesIO()
        chunk.export(buffer, format="mp3")
        return buffer.getvalue()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def render_plot_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"

@st.cache_data(show_spinner="Pre-rendering visualization frames...")
def generate_base64_plots(results, sr, cmap_option):
    # Set dark background style temporarily for beautiful dashboard integration
    plt.style.use('dark_background')
    
    rendered_chunks = []
    for idx, res in enumerate(results):
        offset = res["offset"]
        duration = res["duration"]
        
        # 1. Spectrogram
        fig_spec, ax_spec = plt.subplots(figsize=(8, 3), facecolor='none')
        ax_spec.set_facecolor('none')
        img = ax_spec.imshow(
            res["S_db"], 
            aspect='auto', 
            origin='lower', 
            cmap='magma',
            extent=[offset, offset + duration, 0, sr/2],
            vmin=-80, vmax=0
        )
        ax_spec.set_ylim([0, 8000])
        ax_spec.set_xlabel("time (s)")
        ax_spec.set_ylabel("freq (hz)")
        fig_spec.colorbar(img, ax=ax_spec, format="%+2.f db")
        spec_img = render_plot_to_base64(fig_spec)
        
        # 2. Affordance Field A(t, f)
        fig_af, ax_af = plt.subplots(figsize=(12, 6), facecolor='none')
        ax_af.set_facecolor('none')
        im_af = ax_af.imshow(
            res["field"], 
            aspect='auto', 
            origin='lower', 
            cmap=cmap_option,
            extent=[res["times"][0], res["times"][-1], res["freqs"][0], res["freqs"][-1]]
        )
        ax_af.set_ylim([60, 4000])
        ax_af.set_xlabel("time (s)")
        ax_af.set_ylabel("freq (hz)")
        fig_af.colorbar(im_af, ax=ax_af)
        af_img = render_plot_to_base64(fig_af)
        
        # Mid-frame profile (simplified to only show A and maybe E)
        fig_feat, ax_prof = plt.subplots(figsize=(8, 3), facecolor='none')
        fig_feat.patch.set_facecolor('none')
        mid_idx = res["presence"].shape[1] // 2
        f_mask = res["freqs"] <= 4000
        
        ax_prof.plot(res["freqs"][f_mask], res["field"][f_mask, mid_idx], 'w-', lw=2, label='Affordance (A)')
        ax_prof.plot(res["freqs"][f_mask], res["presence"][f_mask, mid_idx], 'b-', lw=1, alpha=0.5, label='Presence (E)')
        ax_prof.set_xlim([800, 4000])
        ax_prof.set_ylim([0, 1.1])
        ax_prof.legend(loc='upper right', fontsize=8)
        ax_prof.set_title(f"Profile at t={res['times'][mid_idx]:.2f}s")
        ax_prof.set_xlabel("Frequency (Hz)")
        
        feat_img = render_plot_to_base64(fig_feat)
        
        rendered_chunks.append({
            "idx": idx,
            "offset": offset,
            "duration": duration,
            "spec_img": spec_img,
            "af_img": af_img,
            "feat_img": feat_img
        })
        
    return rendered_chunks

@st.cache_data(show_spinner=False)
def process_audio_chunked(file_bytes, file_name, chunk_size=10.0, **af_kwargs):
    duration_total = get_audio_duration(file_bytes, file_name)
    n_chunks = int(np.ceil(duration_total / chunk_size))
    
    sr = 22050
    n_fft = 2048
    hop_length = 512
    total_frames = int(duration_total * sr)
    
    af = AffordanceField(sr=sr, n_fft=n_fft, **af_kwargs)
    
    all_results = []
    
    # Progress container for the first-time run
    progress_container = st.container()
    with progress_container:
        st.write(f"### analyzing {duration_total:.2f}s of audio")
        st.write(f"- total audio frames: {total_frames:,}")
        st.write(f"- total chunks: {n_chunks} ({chunk_size}s each)")
        st.write("- engine: stft + affordance field")
        
        progress_bar = st.progress(0.0)
        status_text = st.empty()
    
    # We'll save the file once to avoid repeated writes
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name

    def process_single_chunk(i):
        offset = i * chunk_size
        current_chunk_size = min(chunk_size, duration_total - offset)
        
        y_chunk, _ = librosa.load(tmp_path, sr=sr, offset=offset, duration=chunk_size)
        
        if len(y_chunk) < n_fft:
            return None
            
        stft = librosa.stft(y_chunk, n_fft=n_fft, hop_length=hop_length, dtype=np.complex64)
        mag = np.abs(stft)
        S_db = librosa.amplitude_to_db(mag, ref=np.max).astype(np.float32)
        
        af_results = af.compute(y_chunk, sr)
        
        return {
            "offset": offset,
            "duration": len(y_chunk) / sr,
            "S_db": S_db,
            "field": af_results["field"],
            "times": af_results["times"] + offset,
            "freqs": af_results["frequencies"],
            "presence": af_results["presence"],
            "persistence": af_results["persistence"],
            "continuity": af_results["continuity"],
            "change": af_results["change"],
            "coherence": af_results["coherence"],
        }

    try:
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_single_chunk, i) for i in range(n_chunks)]
            for i, future in enumerate(futures):
                res = future.result()
                if res is not None:
                    all_results.append(res)
                
                # Streamlit UI updates inside main thread loop
                status_text.text(f"processed chunk {i+1}/{n_chunks}")
                progress_bar.progress((i + 1) / n_chunks)
        
        # Sort results by offset to maintain correct chunk order in case futures completed out of order
        # (Though we are iterating over futures array in order, so it is naturally ordered. But sorting is safe.)
        all_results.sort(key=lambda x: x["offset"])
        
        status_text.text("analysis complete.")
        time.sleep(1)
        progress_container.empty()
            
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return all_results, sr

st.markdown("# [listening](https://github.com/jordan-lenchitz/listening) - spectral affordance analysis (chunked)")

@st.cache_data(show_spinner="Downloading example from GCS...")
def download_example_from_gcs(example_filename):
    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket("jordanlenchitz-net-assets")
    blob = bucket.blob(f"listening-examples/{example_filename}")
    return blob.download_as_bytes()

# example selector
example_options = ["None", "tim waurick (example_one.mp3)", "benedetti_1585.mp3", "jesu.mp3"]
selected_example = st.selectbox("feel free to choose an example", example_options)

# file uploader
uploaded_file = st.file_uploader("you are welcome to upload audio (mp3, wav, flac)", type=["mp3", "wav", "m4a", "flac"])

if selected_example != "None" and uploaded_file is None:
    example_filename = "example_one.mp3" if "tim waurick" in selected_example else selected_example
    try:
        file_data = download_example_from_gcs(example_filename)
        class FakeUploadedFile:
            def __init__(self, name, data):
                self.name = name
                self.data = data
            def getvalue(self):
                return self.data
        uploaded_file = FakeUploadedFile(example_filename, file_data)
    except Exception as e:
        st.error(f"failed to download {example_filename} from GCS: {e}")

# sidebar
st.sidebar.header("analysis settings")

min_chunk = 5.0
max_chunk = 30.0
default_chunk = 10.0

if uploaded_file is not None:
    try:
        file_bytes = uploaded_file.getvalue()
        duration = get_audio_duration(file_bytes, uploaded_file.name)
        if duration < 5.0:
            min_chunk = 1.0
            max_chunk = 3.0
            default_chunk = 2.0
    except Exception as e:
        pass

chunk_size = st.sidebar.slider("chunk size (seconds)", min_chunk, max_chunk, default_chunk)

st.sidebar.subheader("affordance parameters")

expected_singers = st.sidebar.slider("expected singers", 1, 12, 4)
t_val = (expected_singers - 1) / 11.0
t_quad = t_val ** 2

def quad_interp(solo_val, choir_val, t_q):
    return solo_val + (choir_val - solo_val) * t_q

default_mask_rad = float(quad_interp(4.0, 1.0, t_quad))
default_mask_thresh = float(quad_interp(15.0, 5.0, t_quad))
default_harm_w = float(quad_interp(0.2, 1.5, t_quad))
default_cont_erb = float(quad_interp(0.6, 0.2, t_quad))

with st.sidebar.expander("feature weights"):
    w_pres = st.slider("presence weight", 0.0, 2.0, 0.8, 0.1)
    w_pers = st.slider("persistence weight", 0.0, 2.0, 0.5, 0.1)
    w_cont = st.slider("continuity weight", 0.0, 2.0, 0.5, 0.1)
    w_chg = st.slider("change weight", 0.0, 2.0, 1.0, 0.1)
    w_harm = st.slider("harmonic weight", 0.0, 2.0, default_harm_w, 0.1)

with st.sidebar.expander("time constants (ms)"):
    pers_half = st.slider("persistence halflife", 10.0, 200.0, 50.0, 5.0)
    smooth_half = st.slider("smoothing halflife", 10.0, 100.0, 30.0, 5.0)

with st.sidebar.expander("other params"):
    cont_erb = st.slider("continuity neighborhood (ERB)", 0.1, 2.0, default_cont_erb, 0.1)
    on_w = st.slider("onset weight", 0.0, 1.0, 0.65, 0.05)
    off_w = st.slider("offset weight", 0.0, 1.0, 0.35, 0.05)

with st.sidebar.expander("peripheral & masking"):
    mask_rad = st.slider("masking radius (ERB)", 0.5, 5.0, default_mask_rad, 0.1)
    mask_thresh = st.slider("masking threshold (dB)", 0.0, 20.0, default_mask_thresh, 1.0)
    floor_hz = st.slider("harmonic floor (Hz)", 50.0, 1000.0, 100.0, 50.0)
    
af_kwargs = {
    "weight_presence": w_pres,
    "weight_persistence": w_pers,
    "weight_continuity": w_cont,
    "weight_change": w_chg,
    "weight_harmonic": w_harm,
    "persistence_halflife_ms": pers_half,
    "smoothing_halflife_ms": smooth_half,
    "continuity_neighborhood_erb": cont_erb,
    "onset_weight": on_w,
    "offset_weight": off_w,
    "masking_radius_erb": mask_rad,
    "masking_threshold_db": mask_thresh,
    "floor_hz": floor_hz
}

cmap_option = st.sidebar.selectbox(
    "colormap",
    ['viridis', 'plasma', 'inferno', 'magma', 'turbo'],
    index=4
)

if uploaded_file is not None:
    st.write(f"file: {uploaded_file.name}")
    try:
        file_bytes = uploaded_file.getvalue()
        
        results, sr = process_audio_chunked(file_bytes, uploaded_file.name, chunk_size=chunk_size, **af_kwargs)
        
        if not results:
            st.error("failed to process audio")
            st.stop()

        st.success(f"processed {len(results)} chunks")

        # Sidebar selection for playback and visual mode
        st.sidebar.subheader("visualizer settings")
        view_mode = st.sidebar.radio(
            "playback & visual mode", 
            ["interactive dynamic player", "static chunk explorer"], 
            index=0,
            help="interactive dynamic player plays the full audio file with synchronized live visual updates while static chunk explorer displays individual static chunks with isolated controls"
        )

        # Visualization
        st.header("analysis results")

        if view_mode == "interactive dynamic player":
            with st.spinner("Pre-rendering interactive dashboard frames..."):
                # 1. Pre-render all chunk plots to Base64 PNGs
                rendered_chunks = generate_base64_plots(results, sr, cmap_option)
                chunks_json_str = json.dumps(rendered_chunks)
                
                # 2. Encode audio to Base64 URI
                audio_base64 = base64.b64encode(file_bytes).decode("utf-8")
                ext = os.path.splitext(uploaded_file.name)[1].lower()
                mime_type = "audio/mpeg"
                if ext == '.mp3':
                    mime_type = "audio/mp3"
                elif ext == '.wav':
                    mime_type = "audio/wav"
                elif ext == '.flac':
                    mime_type = "audio/flac"
                elif ext == '.m4a':
                    mime_type = "audio/mp4"
                
                audio_data_uri = f"data:{mime_type};base64,{audio_base64}"
                
                # 3. HTML / CSS / JS Template for the custom player
                HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            background-color: #0b0d11;
            color: #eceff1;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 10px;
            overflow-x: hidden;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #0b0d11;
        }
        ::-webkit-scrollbar-thumb {
            background: #1f293d;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #37474f;
        }

        .dashboard-container {
            max-width: 100%;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
        }

        /* Audio Player Card */
        .player-card {
            background: rgba(18, 22, 32, 0.85);
            border: 1px solid #1f2b3e;
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(8px);
        }

        .player-controls-row {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .play-pause-btn {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: linear-gradient(135deg, #7c4dff, #00e5ff);
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(124, 77, 255, 0.4);
            transition: all 0.2s ease;
            flex-shrink: 0;
        }

        .play-pause-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 20px rgba(0, 229, 255, 0.6);
        }

        .play-pause-btn svg {
            width: 18px;
            height: 18px;
            fill: #ffffff;
        }

        .timeline-container {
            flex-grow: 1;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .time-display {
            font-family: monospace;
            font-size: 13px;
            color: #00e5ff;
            min-width: 90px;
            text-shadow: 0 0 4px rgba(0, 229, 255, 0.3);
        }

        .custom-slider {
            -webkit-appearance: none;
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: #1e293b;
            outline: none;
            cursor: pointer;
        }

        .custom-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: #ffffff;
            border: 2px solid #7c4dff;
            cursor: pointer;
            box-shadow: 0 0 8px #7c4dff;
            transition: transform 0.1s;
        }

        .custom-slider::-webkit-slider-thumb:hover {
            transform: scale(1.2);
        }

        .volume-container {
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 110px;
        }

        .volume-btn {
            background: none;
            border: none;
            cursor: pointer;
            color: #cfd8dc;
            display: flex;
            align-items: center;
            padding: 0;
            transition: color 0.2s;
        }

        .volume-btn:hover {
            color: #00e5ff;
        }

        .volume-btn svg {
            width: 18px;
            height: 18px;
            fill: currentColor;
        }

        .volume-slider {
            width: 60px;
        }

        .speed-container {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .speed-btn {
            background: #1e293b;
            border: 1px solid #334155;
            color: #90a4ae;
            font-size: 11px;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-family: 'Rajdhani', sans-serif;
            font-weight: 600;
            transition: all 0.2s;
        }

        .speed-btn.active, .speed-btn:hover {
            background: #7c4dff;
            border-color: #7c4dff;
            color: white;
            box-shadow: 0 0 8px rgba(124, 77, 255, 0.4);
        }

        /* Segmented Timeline */
        .segments-container {
            display: flex;
            gap: 5px;
            width: 100%;
            background: rgba(18, 22, 32, 0.5);
            padding: 5px;
            border-radius: 8px;
            border: 1px solid #1f2b3e;
            margin-bottom: 20px;
            box-sizing: border-box;
        }

        .segment-block {
            flex: 1;
            text-align: center;
            padding: 8px 4px;
            background: #141923;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid transparent;
            box-sizing: border-box;
        }

        .segment-block .title {
            font-family: 'Rajdhani', sans-serif;
            font-weight: 600;
            font-size: 12px;
            color: #cfd8dc;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 2px;
        }

        .segment-block .timespan {
            font-size: 9px;
            color: #78909c;
        }

        .segment-block.active {
            background: linear-gradient(135deg, #1f1a3a, #0c1f2e);
            border: 1px solid #00e5ff;
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);
        }

        .segment-block.active .title {
            color: #00e5ff;
            font-weight: 700;
        }

        .segment-block.active .timespan {
            color: #00e5ff;
        }

        .segment-block:hover:not(.active) {
            background: #1c2331;
            border-color: #37474f;
        }

        /* Grid */
        .plots-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            width: 100%;
        }

        .plot-card {
            background: rgba(18, 22, 32, 0.85);
            border: 1px solid #1f2b3e;
            border-radius: 12px;
            padding: 15px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 6px 24px rgba(0,0,0,0.3);
            backdrop-filter: blur(8px);
            box-sizing: border-box;
        }

        .plot-card.full-width {
            grid-column: span 2;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .card-title {
            font-family: 'Rajdhani', sans-serif;
            font-size: 14px;
            font-weight: 700;
            color: #cfd8dc;
            letter-spacing: 1px;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .card-title .dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #00e5ff;
            box-shadow: 0 0 8px #00e5ff;
        }

        .card-title .dot.purple {
            background-color: #7c4dff;
            box-shadow: 0 0 8px #7c4dff;
        }

        .card-title .dot.green {
            background-color: #00e676;
            box-shadow: 0 0 8px #00e676;
        }

        .card-subtitle {
            font-size: 10px;
            color: #78909c;
        }

        .plot-image-container {
            width: 100%;
            background: #080a0f;
            border-radius: 8px;
            border: 1px solid #151b26;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 250px;
        }

        .plot-card.full-width .plot-image-container {
            height: 320px;
        }

        .plot-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            transition: opacity 0.15s ease-in-out;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Hidden audio element -->
        <audio id="audio-player" src="AUDIO_DATA_URI_PLACEHOLDER"></audio>

        <!-- Player controls -->
        <div class="player-card">
            <div class="player-controls-row">
                <button class="play-pause-btn" id="play-pause-btn" title="Play/Pause">
                    <svg id="play-icon" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    <svg id="pause-icon" viewBox="0 0 24 24" style="display:none;"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                </button>

                <div class="timeline-container">
                    <span class="time-display" id="time-display">00:00 / 00:00</span>
                    <input type="range" class="custom-slider" id="timeline" min="0" max="100" value="0">
                </div>

                <div class="volume-container">
                    <button class="volume-btn" id="volume-btn" title="Mute/Unmute">
                        <svg id="vol-up-icon" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
                        <svg id="vol-mute-icon" viewBox="0 0 24 24" style="display:none;"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.21.05-.42.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/></svg>
                    </button>
                    <input type="range" class="custom-slider volume-slider" id="volume-slider" min="0" max="1" step="0.05" value="0.8">
                </div>

                <div class="speed-container">
                    <button class="speed-btn" data-speed="0.5">0.5x</button>
                    <button class="speed-btn active" data-speed="1.0">1.0x</button>
                    <button class="speed-btn" data-speed="1.5">1.5x</button>
                    <button class="speed-btn" data-speed="2.0">2.0x</button>
                </div>
            </div>
        </div>

        <!-- Segment timeline -->
        <div class="segments-container" id="segments-container"></div>

        <!-- Plots grid -->
        <div class="plots-grid">
            <!-- Spectrogram (STFT) Card -->
            <div class="plot-card">
                <div class="card-header">
                    <div class="card-title">
                        <span class="dot purple"></span>spectrogram (stft)
                    </div>
                    <span class="card-subtitle">time-frequency representation</span>
                </div>
                <div class="plot-image-container">
                    <img id="spec-img" class="plot-image" src="" alt="STFT Spectrogram">
                </div>
            </div>

            <!-- Mid-frame Profile Card -->
            <div class="plot-card">
                <div class="card-header">
                    <div class="card-title">
                        <span class="dot"></span>mid-frame profile
                    </div>
                    <span class="card-subtitle">1D slice</span>
                </div>
                <div class="plot-image-container">
                    <img id="feat-img" class="plot-image" src="" alt="Mid-frame Profile">
                </div>
            </div>

            <!-- Affordance Field Card -->
            <div class="plot-card full-width">
                <div class="card-header">
                    <div class="card-title">
                        <span class="dot green"></span>affordance field A(t,f)
                    </div>
                    <span class="card-subtitle">integrated listening features</span>
                </div>
                <div class="plot-image-container">
                    <img id="af-img" class="plot-image" src="" alt="Affordance Field">
                </div>
            </div>
        </div>
    </div>

    <script>
        const chunks = CHUNKS_DATA_PLACEHOLDER;

        const audio = document.getElementById('audio-player');
        const playPauseBtn = document.getElementById('play-pause-btn');
        const playIcon = document.getElementById('play-icon');
        const pauseIcon = document.getElementById('pause-icon');
        const timeline = document.getElementById('timeline');
        const timeDisplay = document.getElementById('time-display');
        const volumeBtn = document.getElementById('volume-btn');
        const volUpIcon = document.getElementById('vol-up-icon');
        const volMuteIcon = document.getElementById('vol-mute-icon');
        const volumeSlider = document.getElementById('volume-slider');
        const speedBtns = document.querySelectorAll('.speed-btn');

        const specImg = document.getElementById('spec-img');
        
        const afImg = document.getElementById('af-img');\n        const featImg = document.getElementById('feat-img');
        const segmentsContainer = document.getElementById('segments-container');

        let activeChunkIdx = -1;

        // Populate the segments timeline bar
        chunks.forEach((chunk, index) => {
            const block = document.createElement('div');
            block.className = 'segment-block' + (index === 0 ? ' active' : '');
            block.dataset.offset = chunk.offset;
            block.dataset.index = index;
            
            const title = document.createElement('div');
            title.className = 'title';
            title.textContent = 'Chunk ' + (index + 1);
            
            const timespan = document.createElement('div');
            timespan.className = 'timespan';
            timespan.textContent = chunk.offset.toFixed(1) + 's - ' + (chunk.offset + chunk.duration).toFixed(1) + 's';
            
            block.appendChild(title);
            block.appendChild(timespan);
            segmentsContainer.appendChild(block);
        });

        const chunkBlocks = document.querySelectorAll('.segment-block');

        // Format seconds to mm:ss
        function formatTime(seconds) {
            if (isNaN(seconds) || !isFinite(seconds)) return "00:00";
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return (mins < 10 ? "0" : "") + mins + ":" + (secs < 10 ? "0" : "") + secs;
        }

        // Preload all chunk images
        function preloadImages() {
            chunks.forEach(chunk => {
                new Image().src = chunk.spec_img;
                
                new Image().src = chunk.af_img;\n                new Image().src = chunk.feat_img;
            });
        }
        preloadImages();

        // Update display when active chunk changes
        function updateActiveChunk(idx) {
            if (idx === activeChunkIdx) return;
            activeChunkIdx = idx;
            
            const chunk = chunks[idx];
            if (!chunk) return;
            
            // Smooth image crossfade
            specImg.style.opacity = '0.4';
            
            afImg.style.opacity = '0.4';\n            featImg.style.opacity = '0.4';
            
            setTimeout(() => {
                specImg.src = chunk.spec_img;
                
                afImg.src = chunk.af_img;\n                featImg.src = chunk.feat_img;
                
                specImg.style.opacity = '1';
                
                afImg.style.opacity = '1';\n                featImg.style.opacity = '1';
            }, 80);
            
            // Update chunk blocks style
            chunkBlocks.forEach((block, bIdx) => {
                if (bIdx === idx) {
                    block.classList.add('active');
                } else {
                    block.classList.remove('active');
                }
            });
        }

        // Play / Pause Click
        playPauseBtn.addEventListener('click', () => {
            if (audio.paused) {
                audio.play();
            } else {
                audio.pause();
            }
        });

        // Update play/pause icon states
        audio.addEventListener('play', () => {
            playIcon.style.display = 'none';
            pauseIcon.style.display = 'block';
        });

        audio.addEventListener('pause', () => {
            playIcon.style.display = 'block';
            pauseIcon.style.display = 'none';
        });

        // Load metadata to get duration
        audio.addEventListener('loadedmetadata', () => {
            timeDisplay.textContent = formatTime(audio.currentTime) + " / " + formatTime(audio.duration);
            timeline.max = audio.duration;
        });

        // Update timeline slider as audio plays
        audio.addEventListener('timeupdate', () => {
            if (!timeline.dataset.dragging) {
                timeline.value = audio.currentTime;
            }
            timeDisplay.textContent = formatTime(audio.currentTime) + " / " + formatTime(audio.duration);
            
            // Find current chunk index
            const curTime = audio.currentTime;
            let currentIdx = chunks.length - 1;
            for (let i = 0; i < chunks.length; i++) {
                const c = chunks[i];
                if (curTime >= c.offset && curTime < c.offset + c.duration) {
                    currentIdx = i;
                    break;
                }
            }
            updateActiveChunk(currentIdx);
        });

        // Avoid timeline skipping while dragging
        timeline.addEventListener('mousedown', () => {
            timeline.dataset.dragging = 'true';
        });
        timeline.addEventListener('mouseup', () => {
            timeline.dataset.dragging = '';
            audio.currentTime = timeline.value;
        });
        timeline.addEventListener('change', () => {
            audio.currentTime = timeline.value;
        });

        // Volume control
        volumeSlider.addEventListener('input', () => {
            audio.volume = volumeSlider.value;
            if (audio.volume === 0) {
                audio.muted = true;
                volUpIcon.style.display = 'none';
                volMuteIcon.style.display = 'block';
            } else {
                audio.muted = false;
                volUpIcon.style.display = 'block';
                volMuteIcon.style.display = 'none';
            }
        });

        volumeBtn.addEventListener('click', () => {
            audio.muted = !audio.muted;
            if (audio.muted) {
                volUpIcon.style.display = 'none';
                volMuteIcon.style.display = 'block';
                volumeSlider.value = 0;
            } else {
                volUpIcon.style.display = 'block';
                volMuteIcon.style.display = 'none';
                volumeSlider.value = audio.volume;
            }
        });

        // Playback Rate
        speedBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                speedBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                audio.playbackRate = parseFloat(btn.dataset.speed);
            });
        });

        // Click chunk block to seek
        chunkBlocks.forEach(block => {
            block.addEventListener('click', () => {
                const offset = parseFloat(block.dataset.offset);
                audio.currentTime = offset;
                timeline.value = offset;
                if (audio.paused) {
                    audio.play();
                }
            });
        });

        // Initial setup
        updateActiveChunk(0);
        
        // Handle edge case where metadata loaded before event listener attached
        if (audio.readyState >= 1) {
            timeDisplay.textContent = formatTime(audio.currentTime) + " / " + formatTime(audio.duration);
            timeline.max = audio.duration;
        }
    </script>
</body>
</html>
"""
                html_code = HTML_TEMPLATE.replace("CHUNKS_DATA_PLACEHOLDER", chunks_json_str).replace("AUDIO_DATA_URI_PLACEHOLDER", audio_data_uri)
                
                # 4. Render HTML component inside Streamlit
                components.html(html_code, height=1150, scrolling=True)
        else:
            # Select chunk to view
            chunk_idx = st.select_slider("select chunk to visualize", options=range(len(results)), format_func=lambda x: f"chunk {x+1} ({results[x]['offset']:.1f}s)")
            
            res = results[chunk_idx]
            
            st.subheader("spectrogram (stft)")
            fig_spec, ax_spec = plt.subplots(figsize=(12, 4))
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
            
            st.subheader("mid-frame profile")
            fig_feat, ax_prof = plt.subplots(figsize=(12, 4))
            mid_idx = res["presence"].shape[1] // 2
            f_mask = res["freqs"] <= 4000
            
            ax_prof.plot(res["freqs"][f_mask], res["field"][f_mask, mid_idx], 'k-', lw=2, label='Affordance (A)')
            ax_prof.plot(res["freqs"][f_mask], res["presence"][f_mask, mid_idx], 'b-', lw=1, alpha=0.5, label='Presence (E)')
            ax_prof.set_xlim([800, 4000])
            ax_prof.set_ylim([0, 1.1])
            ax_prof.legend(loc='upper right', fontsize=8)
            ax_prof.set_title(f"Profile at t={res['times'][mid_idx]:.2f}s")
            ax_prof.set_xlabel("Frequency (Hz)")
            st.pyplot(fig_feat)
            plt.close(fig_feat)

            # Make the Affordance Field the big picture, full width, at the bottom
            st.subheader(f"affordance field A(t, f)")
            fig_af, ax_af = plt.subplots(figsize=(12, 6))
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
            st.subheader(f"audio playback - chunk {chunk_idx+1}")
            chunk_audio = get_chunk_audio(file_bytes, uploaded_file.name, res["offset"], res["duration"])
            st.audio(chunk_audio, format="audio/mp3")
            
            with st.expander("full audio"):
                st.audio(file_bytes, format=f"audio/{os.path.splitext(uploaded_file.name)[1][1:]}")

    except Exception as e:
        st.error(f"error: {str(e)}")

else:
    st.info("upload audio to begin analysis")
    st.markdown("""
    ### listening affordance analysis
    this tool uses chunked processing to analyze audio through:
    - **stft spectrogram**
    
    - **affordance field** (multi-feature listening representation)
    """)
