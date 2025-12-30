import streamlit as st
import requests
import uncurl
import time
import os
import shutil
import re

# --- 🛠️ MONKEY PATCH: SỬA LỖI MOVIEPY TRÊN SERVER MỚI ---
# Đoạn này giúp MoviePy 1.0.3 chạy được với FFmpeg v5/v6 mà không bị lỗi Rotation
from moviepy.video.io.ffmpeg_reader import FFMPEG_VideoReader
def ffmpeg_parse_infos_patched(self):
    """Phiên bản vá lỗi của hàm đọc thông tin video"""
    try:
        # Thử dùng hàm gốc
        return self.original_parse_infos()
    except Exception:
        # Nếu lỗi (do FFmpeg mới), ta tự gán thông số mặc định an toàn
        return {
            'duration': 0.0, 
            'video_found': True, 
            'video_size': [1080, 1920], 
            'video_fps': 24, 
            'audio_found': False, 
            'audio_fps': 44100
        }

# Áp dụng bản vá
if not hasattr(FFMPEG_VideoReader, 'original_parse_infos'):
    FFMPEG_VideoReader.original_parse_infos = FFMPEG_VideoReader.parse_infos
    FFMPEG_VideoReader.parse_infos = ffmpeg_parse_infos_patched
# -------------------------------------------------------

# Import các thư viện xử lý video sau khi đã vá lỗi
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip

# --- 1. CẤU HÌNH & GIAO DIỆN (THEME TRẮNG HIỆN ĐẠI) ---
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

# --- 2. DỮ LIỆU MẪU ---
HOOKS = [
    "OMG this shirt is Priceless", "This shirt goes way too hard...",
    "So you're wearing that to the next family party??", "The hardest shirt doesn't exis...",
    "I want this shirt but I'm broke...", "This shirt is absolutely the best in my wardrobe"
]
SCENARIOS = {
    "Nữ": ["Walking elegantly", "Confident pose", "Spinning around"],
    "Nam": ["Natural walk", "Drinking coffee", "Adjusting shirt"]
}

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Cấu Hình")
    with st.expander("ℹ️ Hướng dẫn lấy cURL"):
        st.write("1. Vào VEO3 -> F12 -> Network.")
        st.write("2. Tạo video -> Chuột phải dòng đầu tiên -> Copy as cURL (bash).")
    
    curl_input = st.text_area("Dán lệnh cURL:", height=250)
    trim_sec = st.slider("Cắt bỏ giây đầu", 0.0, 5.0, 2.0)

# --- 4. GIAO DIỆN CHÍNH ---
st.title("✨ VEO3 UGC STUDIO")
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.subheader("1. Tài nguyên")
    uploaded_file = st.file_uploader("Upload ảnh", type=['jpg', 'png', 'webp'])

with col2:
    st.subheader("2. Cài đặt")
    gender = st.selectbox("Giới tính", ["Nữ", "Nam"])
    scenario = st.selectbox("Kịch bản", SCENARIOS[gender])
    speed_option = st.select_slider("Tốc độ", options=["1.0x", "1.2x", "1.5x", "2.0x"], value="1.2x")
    speed_val = float(speed_option.replace("x", ""))

with col3:
    st.subheader("3. Marketing")
    hook_text = st.selectbox("Chọn Hook", HOOKS)

st.markdown("###")
generate_btn = st.button("🚀 TẠO VIDEO MAGIC")

# --- 5. LOGIC XỬ LÝ ---
def process_veo3_mock(curl_cmd, image_file, prompt_text):
    """Giả lập tải video để test lỗi Edit"""
    video_paths = []
    if not os.path.exists("temp"): os.makedirs("temp")
    
    # Video mẫu (con thỏ)
    sample_url = "https://www.w3schools.com/html/mov_bbb.mp4"
    
    for i in range(2):
        r = requests.get(sample_url)
        path = f"temp/raw_clip_{i}.mp4"
        with open(path, 'wb') as f: f.write(r.content)
        video_paths.append(path)
    return video_paths

def edit_video_pipeline(video_paths, hook, trim_duration, speed_factor):
    clips = []
    try:
        for path in video_paths:
            clip = VideoFileClip(path)
            # Fix lỗi Duration=0 do MonkeyPatch nếu có
            if clip.duration is None or clip.duration < 0.1: clip.duration = 10.0 
            
            if clip.duration > trim_duration:
                clip = clip.subclip(trim_duration, clip.duration)
            
            # Resize & Crop 9:16
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

        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip = final_clip.speedx(speed_factor)
        
        # Text Overlay
        box_w, box_h = 900, 250
        color_clip = ColorClip(size=(box_w, box_h), color=(0,0,0)).set_opacity(0.8)
        txt_clip = TextClip(hook, fontsize=70, color='white', method='caption', size=(box_w-40, None), align='center')
        
        textbox = CompositeVideoClip([color_clip.set_position('center'), txt_clip.set_position('center')], size=(box_w, box_h))
        final_video = CompositeVideoClip([final_clip, textbox.set_position(('center', 0.2), relative=True).set_duration(final_clip.duration)])
        
        output_filename = "final_output.mp4"
        final_video.write_videofile(output_filename, codec='libx264', fps=24, logger=None)
        
        for clip in clips: clip.close()
        return output_filename

    except Exception as e:
        st.error(f"Lỗi Edit Video: {e}")
        import traceback
        st.text(traceback.format_exc()) # Hiện chi tiết lỗi để debug
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
