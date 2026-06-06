import streamlit as st
import requests
import time
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

st.set_page_config(page_title="listening dissertation demo", layout="wide")

st.title("listening - supercollider edition")

# Sidebar settings
st.sidebar.header("backend status")
try:
    response = requests.get("http://localhost:8000/")
    if response.status_code == 200:
        backend_info = response.json()
        st.sidebar.success(f"connected to {backend_info.get('backend')} engine")
    else:
        st.sidebar.error("backend disconnected")
except Exception:
    st.sidebar.error("backend unreachable")

# File uploader
uploaded_file = st.file_uploader("upload audio for supercollider analysis", type=["mp3", "wav", "m4a", "flac"])

if uploaded_file is not None:
    st.write(f"file {uploaded_file.name} detected. sending to supercollider...")
    
    # 1. Upload to backend
    files = {"audio": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    try:
        resp = requests.post("http://localhost:8000/process", files=files)
        if resp.status_code == 200:
            job_data = resp.json()
            job_id = job_data["job_id"]
            st.info(f"job {job_id} created. processing...")
            
            # 2. Poll for results
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results_area = st.empty()
            
            finished = False
            for i in range(300): # 5 minute timeout
                res_resp = requests.get(f"http://localhost:8000/result/{job_id}")
                if res_resp.status_code == 200:
                    batch_data = res_resp.json()
                    
                    if isinstance(batch_data, dict) and "chunks" in batch_data:
                        chunks_done = len(batch_data["chunks"])
                        total_chunks = batch_data["total_chunks"]
                        progress = chunks_done / total_chunks
                        progress_bar.progress(progress)
                        status_text.text(f"analyzing chunks... {chunks_done}/{total_chunks}")
                        
                        # Update results display
                        with results_area.container():
                            st.header("supercollider analysis results (chunked)")
                            for idx_str in sorted(batch_data["chunks"].keys(), key=int):
                                idx = int(idx_str)
                                chunk_result = batch_data["chunks"][idx_str]
                                with st.expander(f"chunk {idx} ({idx*10}s - {idx*10+10}s)", expanded=(idx == chunks_done - 1)):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**voices**: {chunk_result.get('voices')}")
                                        for track in chunk_result.get('tracks', []):
                                            st.markdown(f"- **track {track['id']}**: {track['freq']} Hz ({track['label']})")
                                    with col2:
                                        af_data = chunk_result.get('affordanceField', [])
                                        if af_data:
                                            fig, ax = plt.subplots(figsize=(4, 2))
                                            ax.bar(range(len(af_data)), af_data, color='blue')
                                            ax.set_title(f"affordance chunk {idx}")
                                            st.pyplot(fig)
                                            plt.close(fig)

                        if batch_data["status"] == "complete":
                            st.success("all chunks complete!")
                            finished = True
                            break
                    else:
                        # Fallback for single result
                        st.success("analysis complete!")
                        st.json(batch_data)
                        finished = True
                        break
                time.sleep(1)
            
            if not finished:
                st.error("analysis timed out or failed")
            
            # Audio player
            st.audio(uploaded_file.getvalue(), format=f"audio/{os.path.splitext(uploaded_file.name)[1][1:]}")
        else:
            st.error(f"failed to start processing: {resp.text}")
    except Exception as e:
        st.error(f"error connecting to backend: {e}")

else:
    st.info("welcome to the listening supercollider dashboard. upload a file to begin.")
    st.markdown("""
    ### how it works
    1. your audio is sent to a **fastapi bridge**
    2. the bridge triggers a headless **supercollider (sclang)** engine
    3. supercollider performs real-time/offline **spectral affordance** analysis
    4. results are sent back via **osc** and displayed here
    """)
