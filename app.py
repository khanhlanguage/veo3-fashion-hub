import streamlit as st
import base64
import json

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="VEO3 Commander", layout="wide", page_icon="🎮")

# --- HÀM XỬ LÝ: BIẾN ẢNH THÀNH MÃ VĂN BẢN (BASE64) ---
def image_to_base64(uploaded_file):
    """Nghiền nát file ảnh thành chuỗi ký tự để vận chuyển qua Text"""
    if uploaded_file is not None:
        try:
            bytes_data = uploaded_file.getvalue()
            base64_str = base64.b64encode(bytes_data).decode('utf-8')
            # Tạo header chuẩn để trình duyệt hiểu đây là ảnh
            return f"data:{uploaded_file.type};base64,{base64_str}"
        except Exception as e:
            st.error(f"Lỗi xử lý ảnh: {e}")
            return None
    return None

# --- GIAO DIỆN NGƯỜI DÙNG ---
st.title("🎮 VEO3 COMMANDER")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. NGUYÊN LIỆU")
    st.info("Upload ảnh và chọn kịch bản tại đây.")
    
    # 1. Upload
    uploaded_file = st.file_uploader("Upload ảnh gốc", type=['jpg', 'png', 'webp', 'jpeg'])
    
    # 2. Settings
    gender = st.selectbox("Giới tính mẫu", ["Woman", "Man", "Person"])
    
    # 3. Kịch bản mẫu
    scenarios = {
        "Đi bộ sang chảnh": "walking elegantly down the street, fashion model style, 4k, cinematic lighting",
        "Uống cà phê": "drinking coffee in a cafe, relaxed atmosphere, highly detailed",
        "Xoay vòng": "spinning around happily, showing off the outfit, full body shot",
        "Tự nhập...": ""
    }
    choice = st.selectbox("Chọn hành động", list(scenarios.keys()))
    
    if choice == "Tự nhập...":
        action = st.text_input("Nhập prompt của bạn (Tiếng Anh):", "")
    else:
        action = scenarios[choice]
        st.caption(f"Prompt: {action}")

    final_prompt = f"A {gender} {action}"

with col2:
    st.header("2. LỆNH VẬN CHUYỂN")
    
    if uploaded_file and final_prompt:
        # Xử lý ảnh
        img_base64 = image_to_base64(uploaded_file)
        
        if img_base64:
            # Đóng gói thành JSON
            payload = {
                "image_data": img_base64,
                "filename": uploaded_file.name,
                "prompt": final_prompt
            }
            json_payload = json.dumps(payload)
            
            st.success("✅ ĐÃ ĐÓNG GÓI XONG!")
            st.warning("👇 Bấm nút nhỏ bên góc phải ô dưới để Copy toàn bộ")
            
            # Hiển thị ô code để copy
            st.code(json_payload, language="json")
            
    else:
        st.info("👈 Vui lòng hoàn tất cột bên trái trước.")
