import streamlit as st
import requests
import uncurl
import time
import os
import shutil
import re
import PIL.Image

# --- 🛠️ VÁ LỖI THÔNG MINH (SMART MONKEY PATCH) ---

# 1. VÁ LỖI PILLOW (Cho Python 3.13+)
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# 2. VÁ LỖI MOVIEPY (Chỉ vá nếu là bản 1.0.3)
try:
    from moviepy.video.io.ffmpeg_reader import FFMPEG_VideoReader
    
    # Kiểm tra xem có hàm parse_infos để vá không
    if hasattr(FFMPEG_VideoReader, 'parse_infos'):
        def ffmpeg_parse_infos_patched(self):
            try:
                return self.original_parse_infos()
            except Exception:
                # Trả về thông số mặc định nếu FFmpeg lỗi
                return {
                    'duration': 10.0, 'video_found': True, 'video_size': [1080, 1920],
                    'video_fps': 24, 'audio_found': False, 'audio_fps': 44100
                }

        # Áp dụng bản vá an toàn
        if not hasattr(FFMPEG_VideoReader, 'original_parse_infos'):
            FFMPEG_VideoReader.original_parse_infos = FFMPEG_VideoReader.parse_infos
            FFMPEG_VideoReader.parse_infos = ffmpeg_parse_infos_patched
except Exception as e:
    # Nếu là bản mới quá thì bỏ qua, không vá nữa
    print(f"Skipping MoviePy patch: {e}")

# -------------------------------------------------------

from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip

# --- CẤU HÌNH ---
st.set_page_config(page_title="VEO3 UGC Studio", page_icon="✨", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #000000; }
    .stTextInput, .stSelectbox, .stFileUploader { border-radius: 10px; }
    div.stButton > button {
        background-color: #000000; color: white; border-radius: 12px;
        padding: 15px 30px; font-size: 20px; font-weight: bold; border: none;
        width: 100%; box-shadow: 0px 4px 12px rgba(0,0,0,0.2);
    }
    div.stButton > button:hover { background-color: #333333; transform: translateY(-2px); }
    </style>
""", unsafe_allow_html=True)

# --- DỮ LIỆU ---
HOOKS = [
    "OMG this shirt is Priceless", "This shirt goes way too hard...",
    "So you're wearing that to the next family party??", "The hardest shirt doesn't exis...",
    "I want this shirt but I'm broke...", "This shirt is absolutely the best in my wardrobe"
]
SCENARIOS = {
    "Nữ": ["Walking elegantly", "Confident pose", "Spinning around"],
    "Nam": ["Natural walk", "Drinking coffee", "Adjusting shirt"]
}

# --- GIAO DIỆN ---
with st.sidebar:
    st.header("⚙️ Cấu Hình")
    curl_input = st.text_area("Dán lệnh cURL (Lấy từ VEO3 -> F12):", height=250)
    trim_sec = st.slider("Cắt bỏ giây đầu", 0.0, 5.0, 2.0)

st.title("✨ VEO3 UGC STUDIO")
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    uploaded_file = st.file_uploader("1. Upload ảnh", type=['jpg', 'png', 'webp'])
with col2:
    gender = st.selectbox("2. Giới tính", ["Nữ", "Nam"])
    scenario = st.selectbox("Kịch bản", SCENARIOS[gender])
    speed_val = float(st.select_slider("Tốc độ", ["1.0x", "1.2x", "1.5x", "2.0x"], value="1.2x").replace("x",""))
with col3:
    hook_text = st.selectbox("3. Chọn Hook", HOOKS)

generate_btn = st.button("🚀 TẠO VIDEO MAGIC")

# --- LOGIC ---
def process_veo3_mock(curl_cmd, image_file, prompt_text):
    if not os.path.exists("temp"): os.makedirs("temp")
    video_paths = []
    # Video mẫu để test
    sample_url = "https://www.w3schools.com/html/mov_bbb.mp4"
    for i in range(2):
        try:
            r = requests.get(sample_url, timeout=10)
            path = f"temp/raw_clip_{i}.mp4"
            with open(path, 'wb') as f: f.write(r.content)
            video_paths.append(path)
        except Exception as e:
            st.error(f"Lỗi tải video mẫu: {e}")
    return video_paths

def edit_video_pipeline(video_paths, hook, trim_duration, speed_factor):
    clips = []
    try:
        for path in video_paths:
            clip = VideoFileClip(path)
            # Fix lỗi duration = 0
            if clip.duration is None or clip.duration < 0.1: clip.duration = 10.0
            
            if clip.duration > trim_duration:
                clip = clip.subclip(trim_duration, clip.duration)
            
            # Crop 9:16
            w, h = clip.size
            target_ratio = 9/16
            if w/h > target_ratio:
                new_w = int(h * target_ratio)
                clip = clip.crop(x1=w/2 - new_w/2, width=new_w, height=h)
            else:
                new_h = int(w / target_ratio)
                clip = clip.crop(y1=h/2 - new_h/2, width=w, height=new_h)
            
            clip = clip.resize(height=1920)
            clips.append(clip)

        if not clips: return None

        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip = final_clip.speedx(speed_factor)
        
        # Text Overlay
        box_w, box_h = 900, 250
        color_clip = ColorClip(size=(box_w, box_h), color=(0,0,0)).set_opacity(0.8)
        
        # Dùng try-catch cho TextClip vì dễ lỗi font
        try:
            txt_clip = TextClip(hook, fontsize=70, color='white', method='caption', size=(box_w-40, None), align='center')
        except:
            # Fallback nếu lỗi font: Dùng font mặc định
            txt_clip = TextClip(hook, fontsize=70, color='white', size=(box_w-40, None), align='center')

        textbox = CompositeVideoClip([color_clip.set_position('center'), txt_clip.set_position('center')], size=(box_w, box_h))
        final_video = CompositeVideoClip([final_clip, textbox.set_position(('center', 0.2), relative=True).set_duration(final_clip.duration)])
        
        output_filename = "final_output.mp4"
        final_video.write_videofile(output_filename, codec='libx264', fps=24, logger=None)
        
        for clip in clips: clip.close()
        return output_filename

    except Exception as e:
        st.error(f"Lỗi Edit Video: {e}")
        return None

if generate_btn:
    if os.path.exists("temp"): shutil.rmtree("temp")
    if not uploaded_file:
        st.warning("⚠️ Chưa upload ảnh!")
    else:
        with st.status("🚀 Đang xử lý...", expanded=True) as status:
            st.write("📡 Kết nối VEO3 (Mock)...")
            raw_videos = process_veo3_mock(curl_input, uploaded_file, f"{scenario}")
            
            if raw_videos:
                st.write(f"🎬 Hậu kỳ: Ghép & Speed {speed_val}x...")
                final_path = edit_video_pipeline(raw_videos, hook_text, trim_sec, speed_val)
                
                if final_path:
                    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)
                    st.success("🎉 Xong!")
                    c1, c2 = st.columns([1, 1])
                    with c1: st.video(final_path)
                    with c2: 
                        with open(final_path, "rb") as f:
                            st.download_button("⬇️ Tải Video", f, "video.mp4", "video/mp4")
