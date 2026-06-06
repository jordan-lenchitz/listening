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
            
            result = None
            for i in range(30): # 30 seconds timeout
                progress_bar.progress((i + 1) / 30)
                status_text.text(f"analyzing... {i+1}s")
                
                res_resp = requests.get(f"http://localhost:8000/result/{job_id}")
                if res_resp.status_code == 200:
                    result = res_resp.json()
                    break
                time.sleep(1)
            
            if result:
                st.success("analysis complete!")
                
                # 3. Display results
                st.header("supercollider analysis results")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("detected voices")
                    st.write(f"count: {result.get('voices')}")
                    for track in result.get('tracks', []):
                        st.markdown(f"**track {track['id']}**: {track['freq']} Hz ({track['label']}) - stability: {track['stability']}")
                
                with col2:
                    st.subheader("spectral affordance field (preview)")
                    af_data = result.get('affordanceField', [])
                    if af_data:
                        fig, ax = plt.subplots()
                        ax.bar(range(len(af_data)), af_data, color='viridis')
                        ax.set_title("affordance magnitudes")
                        st.pyplot(fig)
                        plt.close(fig)
                
                # Audio player
                st.audio(uploaded_file.getvalue(), format=f"audio/{os.path.splitext(uploaded_file.name)[1][1:]}")
            else:
                st.error("analysis timed out or failed")
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
