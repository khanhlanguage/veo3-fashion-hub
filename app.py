import streamlit as st
import requests
import uncurl
import time
import os
import shutil
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip

# --- 1. CẤU HÌNH & GIAO DIỆN (THEME TRẮNG HIỆN ĐẠI) ---
st.set_page_config(page_title="VEO3 UGC Studio", page_icon="✨", layout="wide")

# CSS tùy chỉnh để làm đẹp giao diện (Apple Style)
st.markdown("""
    <style>
    /* Nền trắng chủ đạo */
    .stApp {
        background-color: #FFFFFF;
        color: #000000;
    }
    
    /* Bo tròn các ô nhập liệu */
    .stTextInput, .stSelectbox, .stFileUploader {
        border-radius: 10px;
    }
    
    /* Nút bấm chính màu đen sang trọng */
    div.stButton > button {
        background-color: #000000; /* Màu đen */
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
    
    /* Khung viền nhẹ nhàng */
    .css-1r6slb0 {
        background-color: #F9F9F9;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #E0E0E0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DỮ LIỆU MẪU (PRD) ---
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

# --- 3. SIDEBAR (CẤU HÌNH) ---
with st.sidebar:
    st.header("⚙️ Cấu Hình")
    with st.expander("ℹ️ Hướng dẫn lấy cURL"):
        st.write("1. Vào VEO3 -> F12 -> Tab Network.")
        st.write("2. Tạo 1 video -> Chuột phải dòng 'generate' -> Copy as cURL (bash).")
    
    curl_input = st.text_area("Dán lệnh cURL vào đây:", height=250, help="Dán lệnh copy từ F12 vào đây để đăng nhập.")
    trim_sec = st.slider("Cắt bỏ giây đầu (Giây)", 0.0, 5.0, 2.0, help="Loại bỏ đoạn video bị tĩnh lúc đầu.")

# --- 4. GIAO DIỆN CHÍNH ---
st.title("✨ VEO3 UGC STUDIO")
st.markdown("---")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.subheader("1. Tài nguyên")
    uploaded_file = st.file_uploader("Upload ảnh sản phẩm", type=['jpg', 'png', 'webp'])

with col2:
    st.subheader("2. Cài đặt")
    gender = st.selectbox("Giới tính", ["Nữ", "Nam"])
    scenario = st.selectbox("Kịch bản", SCENARIOS[gender])
    
    # TÍNH NĂNG MỚI: CHỈNH TỐC ĐỘ
    speed_option = st.select_slider(
        "Tốc độ Video",
        options=["1.0x (Bình thường)", "1.2x (Nhanh)", "1.5x (Rất nhanh)", "2.0x (Siêu tốc)"],
        value="1.2x (Nhanh)"
    )
    # Lấy số từ chuỗi (VD: "1.2x..." -> lấy số 1.2)
    speed_val = float(speed_option.split("x")[0])

with col3:
    st.subheader("3. Marketing")
    hook_text = st.selectbox("Chọn câu Hook", HOOKS)

st.markdown("###")
generate_btn = st.button("🚀 TẠO VIDEO MAGIC")

# --- 5. LOGIC XỬ LÝ (BACKEND) ---

def process_veo3_mock(curl_cmd, image_file, prompt_text):
    """
    HÀM GIẢ LẬP (MOCK): Tải video mẫu để test chức năng Edit.
    Sau khi test xong, ta sẽ thay hàm này bằng API thật.
    """
    video_paths = []
    
    # Tạo thư mục tạm
    if not os.path.exists("temp"):
        os.makedirs("temp")

    # Mock: Tải 2 video mẫu từ internet
    sample_urls = [
        "https://www.w3schools.com/html/mov_bbb.mp4", # Scene A
        "https://www.w3schools.com/html/movie.mp4"    # Scene B
    ]
    
    status_text = st.empty()
    
    for i in range(2):
        status_text.info(f"📡 Đang tạo Scene {i+1} từ VEO3 (Giả lập)...")
        time.sleep(1.0) # Giả vờ đợi
        
        # Tải video
        r = requests.get(sample_urls[i])
        path = f"temp/raw_clip_{i}.mp4"
        with open(path, 'wb') as f:
            f.write(r.content)
        video_paths.append(path)
        
    status_text.success("✅ Đã lấy xong source video!")
    return video_paths

def edit_video_pipeline(video_paths, hook, trim_duration, speed_factor):
    """
    Quy trình hậu kỳ: Cắt -> Resize -> Ghép -> Tăng tốc -> Chèn chữ
    """
    clips = []
    try:
        # 1. Xử lý từng clip lẻ
        for path in video_paths:
            clip = VideoFileClip(path)
            
            # Cắt đoạn đầu
            if clip.duration > trim_duration:
                clip = clip.subclip(trim_duration, clip.duration)
            
            # Crop thông minh về 9:16 (1080x1920)
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

        # 2. Ghép nối
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # 3. Áp dụng tốc độ người dùng chọn
        final_clip = final_clip.speedx(speed_factor)
        
        # 4. Tạo Text Overlay
        # Nền đen mờ
        box_w, box_h = 900, 250
        color_clip = ColorClip(size=(box_w, box_h), color=(0,0,0)).set_opacity(0.8)
        
        # Chữ trắng (Dùng method caption để tự xuống dòng và tránh lỗi font)
        txt_clip = TextClip(hook, fontsize=70, color='white', method='caption', size=(box_w-40, None), align='center')
        
        # Ghép chữ vào nền
        textbox = CompositeVideoClip([
            color_clip.set_position('center'),
            txt_clip.set_position('center')
        ], size=(box_w, box_h))
        
        # Đặt vị trí: Cách mép trên 20%
        final_video = CompositeVideoClip([
            final_clip,
            textbox.set_position(('center', 0.2), relative=True).set_duration(final_clip.duration)
        ])
        
        output_filename = "final_output.mp4"
        final_video.write_videofile(output_filename, codec='libx264', fps=24, logger=None)
        
        # Giải phóng bộ nhớ
        for clip in clips:
            clip.close()
            
        return output_filename

    except Exception as e:
        st.error(f"Lỗi Edit Video: {e}")
        return None

# --- 6. CHẠY CHƯƠNG TRÌNH ---
if generate_btn:
    # Dọn dẹp file rác cũ
    if os.path.exists("temp"):
        shutil.rmtree("temp")
        
    if not uploaded_file:
        st.warning("⚠️ Vui lòng upload ảnh sản phẩm trước!")
    else:
        with st.status("🚀 Đang xử lý...", expanded=True) as status:
            # B1: Gọi API (Giả lập)
            st.write("📡 Kết nối VEO3 Ultra...")
            raw_videos = process_veo3_mock(curl_input, uploaded_file, f"{scenario} fashion shot")
            
            # B2: Edit
            if raw_videos:
                st.write(f"🎬 Hậu kỳ: Ghép 2 cảnh & Tăng tốc {speed_val}x...")
                final_path = edit_video_pipeline(raw_videos, hook_text, trim_sec, speed_val)
                
                if final_path:
                    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)
                    
                    st.success("🎉 Video của bạn đã xong!")
                    
                    # Hiển thị và Tải về
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.video(final_path)
                    with c2:
                        with open(final_path, "rb") as f:
                            st.download_button(
                                "⬇️ Tải Video Về (MP4)", 
                                f, 
                                file_name="tiktok_ugc_final.mp4",
                                mime="video/mp4",
                                type="primary"
                            )
