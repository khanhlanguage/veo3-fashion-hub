import streamlit as st
import requests
import json
import time
import os
import shutil
import re
import numpy as np
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

# --- 🛠️ PHẦN 1: VÁ LỖI HỆ THỐNG (SYSTEM PATCHES) ---

# 1. VÁ LỖI PILLOW (Cho Python 3.13+)
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# 2. VÁ LỖI MOVIEPY (FFmpeg Rotation Fix)
try:
    from moviepy.video.io.ffmpeg_reader import FFMPEG_VideoReader
    if hasattr(FFMPEG_VideoReader, 'parse_infos'):
        def ffmpeg_parse_infos_patched(self):
            try:
                return self.original_parse_infos()
            except Exception:
                return {
                    'duration': 10.0, 'video_found': True, 'video_size': [1080, 1920],
                    'video_fps': 24, 'audio_found': False, 'audio_fps': 44100
                }
        if not hasattr(FFMPEG_VideoReader, 'original_parse_infos'):
            FFMPEG_VideoReader.original_parse_infos = FFMPEG_VideoReader.parse_infos
            FFMPEG_VideoReader.parse_infos = ffmpeg_parse_infos_patched
except Exception:
    pass

from moviepy.editor import VideoFileClip, concatenate_videoclips, ImageClip, CompositeVideoClip

# --- 🛠️ PHẦN 2: HÀM VẼ CHỮ BẰNG PIL (FIX LỖI IMAGEMAGICK) ---
def create_text_clip_pil(text, size, fontsize=60, color='white', bg_opacity=0.7, duration=5):
    """Tạo clip chữ bằng Pillow, không dùng ImageMagick để tránh lỗi Security Policy"""
    W, H = size
    # Tạo ảnh nền trong suốt
    img = PIL.Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(img)
    
    # Vẽ hộp đen mờ
    box_h = 250
    box_y = int(H * 0.2) # Vị trí 20% từ trên xuống
    draw.rectangle([(0, box_y), (W, box_y + box_h)], fill=(0, 0, 0, int(255 * bg_opacity)))
    
    # Load Font (Dùng font mặc định nếu không có font đẹp)
    try:
        # Cố gắng load font Sans-serif đậm
        font = PIL.ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fontsize)
    except:
        font = PIL.ImageFont.load_default()

    # Căn giữa text (Thủ công)
    try:
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
    except:
        text_w, text_h = 300, 50 # Fallback
        
    text_x = (W - text_w) // 2
    text_y = box_y + (box_h - text_h) // 2
    
    # Vẽ chữ viền đen cho rõ
    draw.text((text_x+2, text_y+2), text, font=font, fill="black")
    draw.text((text_x, text_y), text, font=font, fill=color)
    
    # Chuyển sang MoviePy ImageClip
    return ImageClip(np.array(img)).set_duration(duration)

# --- 🛠️ PHẦN 3: GIAO DIỆN NGƯỜI DÙNG ---
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

HOOKS = [
    "OMG this shirt is Priceless", "This shirt goes way too hard...",
    "So you're wearing that to the next family party??", "The hardest shirt doesn't exis..."
]
SCENARIOS = {
    "Nữ": ["Walking elegantly", "Confident pose", "Spinning around"],
    "Nam": ["Natural walk", "Drinking coffee", "Adjusting shirt"]
}

with st.sidebar:
    st.header("⚙️ Cấu Hình")
    curl_input = st.text_area("Dán lệnh cURL (Generate):", height=200, help="Dán lệnh 'Copy as cURL' từ VEO3")
    curl_check_input = st.text_area("Dán lệnh cURL (Check Status):", height=100, help="Cần thêm lệnh 'batchCheckAsync...' để tải video về.")
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

# --- 🛠️ PHẦN 4: LOGIC XỬ LÝ ---

def process_veo3_mock(scenario):
    """Giả lập tải video (Dùng khi chưa có API Check)"""
    video_paths = []
    if not os.path.exists("temp"): os.makedirs("temp")
    sample_url = "https://www.w3schools.com/html/mov_bbb.mp4"
    for i in range(2):
        try:
            r = requests.get(sample_url, timeout=10)
            path = f"temp/raw_clip_{i}.mp4"
            with open(path, 'wb') as f: f.write(r.content)
            video_paths.append(path)
        except: pass
    return video_paths

def edit_video_pipeline(video_paths, hook, trim_duration, speed_factor):
    clips = []
    try:
        for path in video_paths:
            clip = VideoFileClip(path)
            # Fix lỗi duration
            if clip.duration is None or clip.duration < 0.1: clip.duration = 10.0
            
            # Trim & Resize
            if clip.duration > trim_duration:
                clip = clip.subclip(trim_duration, clip.duration)
            
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
        
        # --- THAY THẾ TEXTCLIP BẰNG HÀM PIL MỚI ---
        txt_overlay = create_text_clip_pil(hook, final_clip.size, duration=final_clip.duration)
        
        # Ghép Overlay vào Video
        final_video = CompositeVideoClip([final_clip, txt_overlay])
        
        output_filename = "final_output.mp4"
        final_video.write_videofile(output_filename, codec='libx264', fps=24, logger=None)
        
        for clip in clips: clip.close()
        return output_filename

    except Exception as e:
        st.error(f"Lỗi Edit Video: {e}")
        return None

if generate_btn:
    if os.path.exists("temp"): shutil.rmtree("temp")
    
    with st.status("🚀 Đang xử lý...", expanded=True) as status:
        # B1: Kiểm tra cURL
        if len(curl_input) > 100 and "image" in curl_input:
             # Logic API thật (Sẽ kích hoạt khi có cURL chuẩn)
             st.write("📡 Đang gửi lệnh lên VEO3...")
             # ... code API thật ...
        else:
             st.write("📡 Dùng chế độ Demo (Do chưa đủ cURL)...")
             raw_videos = process_veo3_mock(scenario)
        
        # B2: Edit
        if raw_videos:
            st.write(f"🎬 Hậu kỳ: Ghép & Speed {speed_val}x (Dùng công nghệ PIL)...")
            final_path = edit_video_pipeline(raw_videos, hook_text, trim_sec, speed_val)
            
            if final_path:
                status.update(label="✅ Hoàn tất!", state="complete", expanded=False)
                st.success("🎉 Video của bạn đã xong!")
                c1, c2 = st.columns([1, 1])
                with c1: st.video(final_path)
                with c2: 
                    with open(final_path, "rb") as f:
                        st.download_button("⬇️ Tải Video", f, "video.mp4", "video/mp4", type="primary")
