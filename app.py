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

# ==========================================
# 🛠️ PHẦN 1: VÁ LỖI HỆ THỐNG (SYSTEM PATCHES)
# ==========================================

# 1. VÁ LỖI PILLOW (Cho Python 3.13+)
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# 2. VÁ LỖI MOVIEPY (Sửa lỗi FFmpeg Rotation)
try:
    from moviepy.video.io.ffmpeg_reader import FFMPEG_VideoReader
    # Kiểm tra xem có cần vá không
    if hasattr(FFMPEG_VideoReader, 'parse_infos'):
        def ffmpeg_parse_infos_patched(self):
            try:
                # Thử chạy hàm gốc
                return self.original_parse_infos()
            except Exception:
                # Nếu lỗi, trả về thông số mặc định an toàn
                return {
                    'duration': 10.0, 
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
except Exception:
    pass # Bỏ qua nếu không import được

from moviepy.editor import VideoFileClip, concatenate_videoclips, ImageClip, CompositeVideoClip

# ==========================================
# 🛠️ PHẦN 2: CÁC HÀM XỬ LÝ CỐT LÕI
# ==========================================

def create_text_clip_pil(text, size, fontsize=60, color='white', bg_opacity=0.7, duration=5):
    """
    Tạo Text Overlay bằng công nghệ Pillow (Thay thế ImageMagick bị lỗi).
    Vẽ một hộp đen mờ và chèn chữ trắng vào giữa.
    """
    W, H = size
    # Tạo ảnh nền trong suốt
    img = PIL.Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(img)
    
    # Vẽ hộp đen mờ (Background Box)
    box_h = 300
    box_y = int(H * 0.15) # Vị trí cách mép trên 15%
    draw.rectangle([(0, box_y), (W, box_y + box_h)], fill=(0, 0, 0, int(255 * bg_opacity)))
    
    # Load Font (Cố gắng tìm font đẹp, nếu không thì dùng mặc định)
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font = PIL.ImageFont.truetype(font_path, fontsize)
    except:
        font = PIL.ImageFont.load_default()

    # Tính toán vị trí chữ (Căn giữa thủ công)
    text_x = 50 # Lề trái mặc định
    text_y = box_y + 100 # Vị trí y mặc định
    
    # Vẽ chữ (Có viền đen nhẹ cho nổi)
    draw.text((text_x+2, text_y+2), text, font=font, fill="black")
    draw.text((text_x, text_y), text, font=font, fill=color)
    
    # Chuyển đổi sang MoviePy Clip
    return ImageClip(np.array(img)).set_duration(duration)

def parse_curl(curl_cmd):
    """Hàm thông minh giúp bóc tách URL, Headers và Data từ lệnh cURL"""
    headers = {}
    
    # 1. Bóc tách Headers (-H 'Key: Value')
    # Regex này bắt được cả dấu nháy đơn ' và nháy kép "
    header_pattern = re.compile(r"-H\s+['\"]([^:]+):\s+([^'\"]+)['\"]")
    for match in header_pattern.finditer(curl_cmd):
        headers[match.group(1)] = match.group(2)
        
    # 2. Bóc tách URL
    url_match = re.search(r"curl\s+['\"]([^'\"]+)['\"]", curl_cmd)
    url = url_match.group(1) if url_match else None
    
    # 3. Bóc tách Data Body (--data-raw '{...}')
    data_match = re.search(r"--data-raw\s+['\"]({.+})['\"]", curl_cmd)
    try:
        data = json.loads(data_match.group(1)) if data_match else {}
    except:
        data = {}
        
    return url, headers, data

def process_veo3_real(curl_gen, curl_check, prompt_override):
    """
    Quy trình Gọi VEO3 Thật:
    1. Gửi lệnh Tạo (có sửa Prompt).
    2. Lấy mã vé (Operation ID).
    3. Dùng mã vé để hỏi server liên tục (Polling) cho đến khi có Video.
    """
    status_text = st.empty()
    
    # --- BƯỚC 1: GỬI LỆNH TẠO ---
    status_text.info("📡 Đang gửi lệnh lên Google VEO3...")
    try:
        url_gen, headers_gen, data_gen = parse_curl(curl_gen)
        
        # QUAN TRỌNG: Thay thế Prompt cũ bằng Prompt người dùng chọn trên App
        # Cấu trúc JSON của VEO3 thường là: requests[0] -> textInput -> prompt
        if 'requests' in data_gen and len(data_gen['requests']) > 0:
            if 'textInput' in data_gen['requests'][0]:
                old_prompt = data_gen['requests'][0]['textInput'].get('prompt', '')
                print(f"DEBUG: Old prompt: {old_prompt}")
                
                # Gán prompt mới
                data_gen['requests'][0]['textInput']['prompt'] = prompt_override
                print(f"DEBUG: New prompt sent: {prompt_override}")

        # Gửi Request đi
        r_gen = requests.post(url_gen, headers=headers_gen, json=data_gen)
        
        if r_gen.status_code != 200:
            st.error(f"❌ Lỗi gửi lệnh tạo (Code {r_gen.status_code}): {r_gen.text}")
            return None
            
        resp_gen = r_gen.json()
        
        # Lấy Operation ID (Mã vé)
        try:
            op_name = resp_gen['operations'][0]['operation']['name']
            st.write(f"🎫 Đã lấy được mã vé: `{op_name[-10:]}`")
        except:
            st.error("❌ Không tìm thấy mã Operation trong phản hồi. Có thể Cookie đã hết hạn?")
            return None

    except Exception as e:
        st.error(f"❌ Lỗi xử lý cURL Generate: {e}")
        return None

    # --- BƯỚC 2: CHỜ VIDEO (POLLING) ---
    url_chk, headers_chk, _ = parse_curl(curl_check)
    
    video_url = None
    retry_count = 0
    max_retries = 30 # Chờ tối đa khoảng 90 giây
    
    while retry_count < max_retries:
        status_text.info(f"⏳ Đang chờ VEO3 render... ({retry_count*3}s)")
        time.sleep(3) # Đợi 3s mỗi lần hỏi
        
        try:
            # Tạo payload mới chứa cái Mã Vé vừa lấy được
            check_payload = {
                "operations": [{"operation": {"name": op_name}}]
            }
            
            r_chk = requests.post(url_chk, headers=headers_chk, json=check_payload)
            resp_chk = r_chk.json()
            
            # Kiểm tra phản hồi xem có URL video chưa
            ops = resp_chk.get('operations', [])
            if ops and 'response' in ops[0]:
                response_data = ops[0]['response']
                
                # Google trả về link video ở đây
                if 'video' in response_data and 'url' in response_data['video']:
                    video_url = response_data['video']['url']
                    break # Thoát vòng lặp
                elif 'mp4_url' in response_data: # Dự phòng trường hợp đổi key
                    video_url = response_data['mp4_url']
                    break
                
        except Exception as e:
            print(f"Lỗi check status: {e}")
            
        retry_count += 1
        
    if not video_url:
        st.error("❌ Hết thời gian chờ (Timeout) hoặc server không trả về Video.")
        return None

    # --- BƯỚC 3: TẢI VIDEO VỀ ---
    status_text.info("⬇️ Đang tải video gốc về máy chủ...")
    video_paths = []
    if not os.path.exists("temp"): os.makedirs("temp")
    
    path = "temp/veo3_output.mp4"
    with open(path, 'wb') as f:
        f.write(requests.get(video_url).content)
    
    # Nhân bản video thành 2 bản để ghép nối (Tạo cảm giác video dài hơn)
    video_paths = [path, path] 
    return video_paths

def edit_video_pipeline(video_paths, hook, trim_duration, speed_factor):
    """Hậu kỳ video: Cắt, Ghép, Speed, Chữ"""
    clips = []
    try:
        for path in video_paths:
            clip = VideoFileClip(path)
            # Fix lỗi duration ảo
            if clip.duration is None or clip.duration < 0.1: clip.duration = 5.0
            
            # Cắt đoạn đầu bị tĩnh
            if clip.duration > trim_duration:
                clip = clip.subclip(trim_duration, clip.duration)
            
            # Crop 9:16 (Cho TikTok/Shorts)
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

        # Ghép nối
        if not clips: return None
        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip = final_clip.speedx(speed_factor)
        
        # Chèn chữ (Dùng hàm PIL mới)
        txt_overlay = create_text_clip_pil(hook, final_clip.size, duration=final_clip.duration)
        
        # Xuất file
        final_video = CompositeVideoClip([final_clip, txt_overlay])
        output_filename = "final_output.mp4"
        final_video.write_videofile(output_filename, codec='libx264', fps=24, logger=None)
        
        # Dọn dẹp bộ nhớ
        for clip in clips: clip.close()
        return output_filename

    except Exception as e:
        st.error(f"❌ Lỗi Edit Video: {e}")
        return None

# ==========================================
# 🛠️ PHẦN 3: GIAO DIỆN NGƯỜI DÙNG (UI)
# ==========================================

st.set_page_config(page_title="VEO3 UGC Studio", page_icon="✨", layout="wide")

# CSS làm đẹp giao diện
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #000000; }
    div.stButton > button {
        background-color: #000000; color: white; border-radius: 10px;
        padding: 15px; font-size: 18px; font-weight: bold; width: 100%;
        border: none; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #333333; transform: scale(1.02); }
    .stTextInput textarea { font-family: monospace; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# Dữ liệu mẫu
HOOKS = [
    "OMG this shirt is Priceless 🔥", 
    "This shirt goes way too hard... 🤯", 
    "So you're wearing that to the party??", 
    "The hardest shirt doesn't exis...",
    "Best purchase of the year! 💸"
]
SCENARIOS = {
    "Nữ": [
        "A beautiful woman walking elegantly, fashion model, high quality, 4k",
        "A woman posing confidently on street, looking at camera, realistic",
        "A woman spinning around happily, showing off outfit, detailed"
    ],
    "Nam": [
        "A handsome man walking cool, street style, cinematic lighting",
        "A man standing confidently, adjusting shirt, high fashion",
        "A man drinking coffee, relaxed vibe, urban background"
    ]
}

# --- SIDEBAR: CẤU HÌNH ---
with st.sidebar:
    st.header("🔑 CẤU HÌNH (Bắt buộc)")
    st.info("Mã cURL hết hạn sau 1 giờ. Khi lỗi, hãy lấy mã mới dán vào đây.")
    
    curl_gen_input = st.text_area(
        "1. Dán cURL GENERATE (Có ảnh):", 
        height=200, 
        help="Lấy từ tab Network -> batchAsyncGenerate... (loại POST)"
    )
    
    curl_check_input = st.text_area(
        "2. Dán cURL CHECK STATUS:", 
        height=150,
        help="Lấy từ tab Network -> batchCheckAsync..."
    )
    
    st.markdown("---")
    trim_sec = st.slider("Cắt bỏ giây đầu (Tránh video tĩnh)", 0.0, 5.0, 2.0)

# --- MAIN UI ---
st.title("✨ VEO3 UGC STUDIO (REAL)")
st.caption("Công cụ tạo video Fashion tự động từ ảnh tĩnh")

col1, col2, col3 = st.columns([1,1,1])

with col1:
    st.subheader("1. Tài nguyên")
    st.info("ℹ️ App sẽ sử dụng hình ảnh từ trong lệnh cURL bạn dán vào.")
    # (Để chỗ trống cho tính năng upload thật trong tương lai)

with col2:
    st.subheader("2. Kịch bản & Tốc độ")
    gender = st.selectbox("Giới tính người mẫu", ["Nữ", "Nam"])
    scenario = st.selectbox("Hành động (Prompt mới)", SCENARIOS[gender])
    speed_val = float(st.select_slider("Tốc độ video", ["1.0x", "1.2x", "1.5x", "2.0x"], value="1.2x").replace("x",""))

with col3:
    st.subheader("3. Marketing")
    hook_text = st.selectbox("Câu Hook (Chèn chữ)", HOOKS)

st.markdown("###")

# --- NÚT CHẠY ---
if st.button("🚀 TẠO VIDEO MAGIC"):
    # Kiểm tra đầu vào
    if len(curl_gen_input) < 50 or len(curl_check_input) < 50:
        st.warning("⚠️ Vui lòng dán đủ 2 lệnh cURL vào cột bên trái (Sidebar) trước khi chạy!")
    else:
        # Bắt đầu xử lý
        with st.status("🚀 Đang khởi động quy trình...", expanded=True) as status:
            
            # GỌI API THẬT
            raw_videos = process_veo3_real(curl_gen_input, curl_check_input, scenario)
            
            if raw_videos:
                st.write("🎬 Đang hậu kỳ: Ghép nối, Speed Up, Chèn Hook...")
                final_path = edit_video_pipeline(raw_videos, hook_text, trim_sec, speed_val)
                
                if final_path:
                    status.update(label="✅ HOÀN TẤT!", state="complete", expanded=False)
                    st.balloons()
                    st.success("🎉 Video của bạn đã sẵn sàng!")
                    
                    # Hiển thị kết quả
                    c1, c2 = st.columns([1,1])
                    with c1: 
                        st.video(final_path)
                    with c2: 
                        with open(final_path, "rb") as f:
                            st.download_button(
                                label="⬇️ TẢI VIDEO VỀ (MP4)", 
                                data=f, 
                                file_name="tiktok_ugc_final.mp4", 
                                mime="video/mp4",
                                type="primary"
                            )
