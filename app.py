import streamlit as st
import requests
import uncurl
import time
import os
import shutil
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip

# --- 1. CONFIGURATION & STYLING (MODERN LIGHT THEME) ---
st.set_page_config(page_title="VEO3 UGC Studio", page_icon="✨", layout="wide")

# Custom CSS for Apple-esque Minimalist Design
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #FFFFFF;
        color: #000000;
    }
    
    /* Inputs & Selectboxes */
    .stTextInput, .stSelectbox, .stFileUploader {
        border-radius: 10px;
    }
    
    /* Primary Button Styling */
    div.stButton > button {
        background-color: #000000; /* Deep Black */
        color: white;
        border-radius: 12px;
        padding: 15px 30px;
        font-size: 20px;
        font-weight: bold;
        border: none;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #333333;
        transform: translateY(-2px);
    }
    
    /* Card-like containers */
    .css-1r6slb0 {
        background-color: #F9F9F9;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #E0E0E0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA CONSTANTS ---
HOOKS = [
    "OMG this shirt is Priceless",
    "This is absolutely the best one I have seen yet",
    "This shirt goes way too hard...",
    "So you're wearing that to the next family party??",
    "The hardest shirt doesn't exis...",
    "I want this shirt but I'm broke...",
    "I never bought something so fast like this shirt",
    "This shirt is absolutely the best in my wardrobe",
    "How can this shirt have this price? It can fool an...",
    "Omg!! This shirt is fire asf!!"
]

SCENARIOS = {
    "Nữ": ["Walking elegantly", "Confident pose", "Spinning around", "Adjusting collar"],
    "Nam": ["Natural walk", "Drinking coffee", "Adjusting shirt", "Hands in pocket"]
}

# --- 3. SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")
    with st.expander("ℹ️ How to get cURL?"):
        st.write("1. Go to VEO3 -> F12 -> Network.")
        st.write("2. Create a video -> Right click request -> Copy as cURL (bash).")
    
    curl_input = st.text_area("Paste VEO3 cURL Command Here:", height=250, help="Paste the raw cURL command to authenticate.")
    trim_sec = st.slider("Trim Start (Seconds)", 0.0, 5.0, 2.0, help="Remove static intro")

# --- 4. MAIN INTERFACE ---
st.title("✨ VEO3 UGC STUDIO")
st.markdown("---")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.subheader("1. Asset")
    uploaded_file = st.file_uploader("Upload Product Image", type=['jpg', 'png', 'webp'])

with col2:
    st.subheader("2. Settings")
    gender = st.selectbox("Gender", ["Nữ", "Nam"])
    scenario = st.selectbox("Scenario", SCENARIOS[gender])
    
    # SPEED CONTROL FEATURE
    speed_option = st.select_slider(
        "Video Speed Multiplier",
        options=["1.0x (Normal)", "1.2x (Fast)", "1.5x (Very Fast)", "2.0x (Hyper)"],
        value="1.2x (Fast)"
    )
    # Extract float value from string (e.g., "1.2x" -> 1.2)
    speed_val = float(speed_option.split("x")[0])

with col3:
    st.subheader("3. Marketing")
    hook_text = st.selectbox("Select Hook Text", HOOKS)

st.markdown("###")
generate_btn = st.button("🚀 GENERATE VIDEO MAGIC")

# --- 5. BACKEND LOGIC ---

def process_veo3_mock(curl_cmd, image_file, prompt_text):
    """
    MOCK FUNCTION: Simulates VEO3 API call by downloading sample videos.
    REPLACE THIS with real API logic once UI is verified.
    """
    video_paths = []
    
    # Create temp directory
    if not os.path.exists("temp"):
        os.makedirs("temp")

    # Mock: Download 2 sample videos from W3Schools/Internet
    sample_urls = [
        "https://www.w3schools.com/html/mov_bbb.mp4", # Scene A
        "https://www.w3schools.com/html/movie.mp4"    # Scene B
    ]
    
    status_text = st.empty()
    
    for i in range(2):
        status_text.info(f"📡 Generating Scene {i+1} via VEO3 (Simulated)...")
        time.sleep(1.5) # Fake wait time
        
        # Download mock video
        r = requests.get(sample_urls[i])
        path = f"temp/raw_clip_{i}.mp4"
        with open(path, 'wb') as f:
            f.write(r.content)
        video_paths.append(path)
        
    status_text.success("✅ VEO3 Generation Complete!")
    return video_paths

def edit_video_pipeline(video_paths, hook, trim_duration, speed_factor):
    """
    Processes the raw clips: Trim -> Resize -> Concat -> Speed -> Overlay
    """
    clips = []
    try:
        # 1. Process individual clips
        for path in video_paths:
            clip = VideoFileClip(path)
            
            # Trim static start
            if clip.duration > trim_duration:
                clip = clip.subclip(trim_duration, clip.duration)
            
            # Smart Crop to 9:16 (1080x1920)
            target_ratio = 9/16
            current_ratio = clip.w / clip.h
            
            if current_ratio > target_ratio:
                new_w = int(clip.h * target_ratio)
                clip = clip.crop(x1=clip.w/2 - new_w/2, width=new_w, height=clip.h)
            else:
                new_h = int(clip.w / target_ratio)
                clip = clip.crop(y1=clip.h/2 - new_h/2, width=clip.w, height=new_h)
            
            clip = clip.resize(height=1920)
            clips.append(clip)

        # 2. Concatenate
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # 3. Apply User Selected Speed
        final_clip = final_clip.speedx(speed_factor)
        
        # 4. Create Text Overlay
        # Box background
        box_w, box_h = 900, 250
        color_clip = ColorClip(size=(box_w, box_h), color=(0,0,0)).set_opacity(0.8)
        
        # Text (Caption method avoids ImageMagick font errors)
        txt_clip = TextClip(hook, fontsize=70, color='white', method='caption', size=(box_w-40, None), align='center')
        
        # Composite Box + Text
        textbox = CompositeVideoClip([
            color_clip.set_position('center'),
            txt_clip.set_position('center')
        ], size=(box_w, box_h))
        
        # Position at Top 20%
        final_video = CompositeVideoClip([
            final_clip,
            textbox.set_position(('center', 0.2), relative=True).set_duration(final_clip.duration)
        ])
        
        output_filename = "final_output.mp4"
        final_video.write_videofile(output_filename, codec='libx264', fps=24, logger=None)
        
        # Clean up clips to free memory
        for clip in clips:
            clip.close()
            
        return output_filename

    except Exception as e:
        st.error(f"Editing Error: {e}")
        return None

# --- 6. EXECUTION ---
if generate_btn:
    # Cleanup old temp files
    if os.path.exists("temp"):
        shutil.rmtree("temp")
        
    if not uploaded_file:
        st.warning("⚠️ Please upload a product image first!")
    else:
        with st.status("🚀 Processing...", expanded=True) as status:
            # Step 1: Call API (Mocked for now)
            st.write("📡 Connecting to VEO3 Ultra...")
            raw_videos = process_veo3_mock(curl_input, uploaded_file, f"{scenario} fashion shot")
            
            # Step 2: Edit
            if raw_videos:
                st.write(f"🎬 Editing: Merging 2 Scenes & Speeding up {speed_val}x...")
                final_path = edit_video_pipeline(raw_videos, hook_text, trim_sec, speed_val)
                
                if final_path:
                    status.update(label="✅ Complete!", state="complete", expanded=False)
                    
                    st.success("🎉 Your Video is Ready!")
                    
                    # Columns for Video & Download
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.video(final_path)
                    with c2:
                        with open(final_path, "rb") as f:
                            st.download_button(
                                "⬇️ Download Video (MP4)", 
                                f, 
                                file_name="tiktok_ugc_final.mp4",
                                mime="video/mp4",
                                type="primary" # Makes button standout
                            )
