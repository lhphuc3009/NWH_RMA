import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import requests
import io
import plotly.express as px
from rma_ai import query_openai
from rma_ai import chuan_hoa_ten_cot
from rma_utils import bo_loc_da_nang, ensure_time_columns, find_col
from rma_utils import render_bo_loc_sidebar, apply_bo_loc
import time
def export_excel_button(df, filename="bao_cao_rma.xlsx", label="📥 Tải file Excel"):
    if df.empty:
        return
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="RMA_Report")
    buffer.seek(0)
    st.download_button(
        label=label,
        data=buffer.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
import yaml

def load_users_config():
    config = None

    # Cách 1: Dùng biến môi trường (Vercel)
    if "USERS_YAML" in os.environ:
        try:
            config = yaml.safe_load(os.environ["USERS_YAML"])
            print("🔐 Đã load users từ biến môi trường (Vercel)")
        except Exception as e:
            print("❌ Lỗi đọc USERS_YAML:", e)

    # Cách 2: Dùng st.secrets (Streamlit Cloud)
    elif "users" in st.secrets:
        try:
            config = st.secrets["users"]
            print("🔐 Đã load users từ st.secrets (Streamlit Cloud)")
        except Exception as e:
            print("❌ Lỗi đọc st.secrets:", e)

    # Cách 3: Đọc từ file local (Local dev)
    elif os.path.exists("data/users.yaml"):
        try:
            with open("data/users.yaml", "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
            print("📁 Đã load users từ file local")
        except Exception as e:
            print("❌ Lỗi đọc file users.yaml:", e)

    else:
        print("⚠️ Không tìm thấy cấu hình đăng nhập người dùng")
    
    return config

users = load_users_config()
if users is None:
    st.error("Không tìm thấy cấu hình đăng nhập!")
    st.stop()


# === Đăng nhập đơn giản ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = None

if st.session_state.logged_in != True:
    st.title("🔐 Đăng nhập hệ thống RMA")
    username = st.text_input("👤 Tên đăng nhập")
    password = st.text_input("🔑 Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        user = users.get(username)
        if user and user["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = user["role"]
            st.session_state.full_name = user.get("name", username)
            st.session_state.debug_mode = (user["role"] == "admin")
            st.rerun()
        else:
            st.error("Sai tên đăng nhập hoặc mật khẩu.")
    st.stop()

import rma_query_templates

load_dotenv()

st.set_page_config(page_title="Trợ lý RMA AI", layout="wide")
st.title("🧠 RMA – Dữ Liệu Bảo Hành")

# === 1. Load dữ liệu từ Google Sheet ===
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1fWFLZWyCAXn_B8jcZ0oY4KhJ8krbLPsH/export?format=csv"

def read_google_sheet(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode("utf-8")))
            df.columns = [col.strip() for col in df.columns]
            return ensure_time_columns(df)
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu: {e}")
    return pd.DataFrame()

data = read_google_sheet(GOOGLE_SHEET_URL)
df_raw = read_google_sheet(GOOGLE_SHEET_URL)
df_raw = chuan_hoa_ten_cot(df_raw)

if data.empty:
    st.stop()


# === 2. Tạo tabs giao diện mới ===
# Xác định vai trò người dùng từ session
role = st.session_state.get("role", "guest")

# Tạo danh sách label động theo phân quyền
tab_labels = ["📊 Dữ liệu RMA"]
if role in ["admin", "mod"]:
    tab_labels.append("🤖 Trợ lý AI")
tab_labels.append("📋 Báo cáo & Thống kê")

# Gán tab theo số lượng
tabs = st.tabs(tab_labels)
tab1 = tabs[0]
if role in ["admin", "mod"]:
    tab2 = tabs[1]
    tab3 = tabs[2]
else:
    tab2 = None
    tab3 = tabs[1]
with st.sidebar:
    role = st.session_state.get("role", "guest")
    # 👋 Chào người dùng
    full_name = st.session_state.get("full_name", "---")
    st.markdown(f"## 👋 Xin chào, **:green[{full_name}]** !")

    if st.button("🚪 Đăng xuất"):
        st.session_state.logged_in = None
        st.rerun()

    st.markdown("---")

    # 📕 Bộ lọc nâng cao
    filters = render_bo_loc_sidebar(data, prefix_key="main")

    # ⚙️ Tùy chọn gửi AI (thu gọn mặc định)
    if role in ["admin", "mod"]:
        with st.expander("⚙️ Tuỳ chọn gửi AI", expanded=False):
            max_rows = st.slider("📌 Giới hạn số dòng gửi AI", 50, 1000, 200)

# Áp dụng lọc sau khi lấy lựa chọn
data_filtered = apply_bo_loc(data, filters)

# === TAB 1: Xem và lọc dữ liệu ===
with tab1:
    st.header("📊 Bảng dữ liệu và bộ lọc")

    # === TÌM KIẾM NHANH ===
    with st.expander("🔍 Tìm kiếm nhanh"):
        search_mode = st.radio("Chọn loại tìm kiếm:", ["🔎 Theo khách hàng", "🔎 Theo sản phẩm", "🔎 Theo số serial"], horizontal=True)
        keyword = st.text_input("Nhập từ khóa cần tìm:")

        # GỢI Ý KHỚP
        if keyword:
            if search_mode == "🔎 Theo khách hàng":
                col_name = find_col(data.columns, "khách hàng")
            elif search_mode == "🔎 Theo sản phẩm":
                col_name = find_col(data.columns, "sản phẩm")
            else:
                col_name = None

            if col_name:
                all_values = data[col_name].dropna().unique().tolist()
                suggestions = [s for s in all_values if keyword.lower() in s.lower()]
                if suggestions:
                    st.markdown('<div style="font-size: 0.85rem; color: #aaa;"><b>🔎 Gợi ý khớp:</b></div>', unsafe_allow_html=True)
                    for s in suggestions[:3]:
                        st.markdown(f'<div style="font-size: 0.85rem; color: #ccc;">• {s}</div>', unsafe_allow_html=True)

        # LỌC DỮ LIỆU THEO TỪ KHÓA
        if keyword:
            keyword_lower = keyword.lower()
            if search_mode == "🔎 Theo khách hàng":
                col_name = find_col(data_filtered.columns, "khách hàng")
            elif search_mode == "🔎 Theo sản phẩm":
                col_name = find_col(data_filtered.columns, "sản phẩm")
            else:
                col_name = find_col(data_filtered.columns, "serial")

            if col_name:
                data_filtered = data_filtered[
                    data_filtered[col_name].astype(str).str.lower().str.contains(keyword_lower, na=False)
                ]
            else:
                st.warning("Không tìm thấy cột phù hợp để tìm kiếm.")

    # === LỌC THEO LOẠI DỊCH VỤ ===
    with st.expander("📌 Lọc theo loại dịch vụ"):
        col_dichvu = find_col(data_filtered.columns, "loại dịch vụ")
        if col_dichvu:
            unique_types = data_filtered[col_dichvu].dropna().unique().tolist()
            selected_types = st.multiselect("Chọn loại dịch vụ:", unique_types)
            if selected_types:
                data_filtered = data_filtered[data_filtered[col_dichvu].isin(selected_types)]

    # === LỌC THEO LỖI KỸ THUẬT ===
    with st.expander("📌 Lọc theo kỹ thuật viên"):
        col_loi = find_col(data_filtered.columns, "KTV")
        if col_loi:
            unique_errors = data_filtered[col_loi].dropna().unique().tolist()
            selected_errors = st.multiselect("Chọn KTV cần lọc:", unique_errors)
            if selected_errors:
                data_filtered = data_filtered[data_filtered[col_loi].isin(selected_errors)]

    # === HIỂN THỊ KẾT QUẢ & TẢI FILE ===
    if keyword or selected_types or selected_errors:
        st.markdown(f"**Số dòng sau khi lọc:** {len(data_filtered)} / {len(data)}")
        st.dataframe(data_filtered, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            data_filtered.to_excel(writer, index=False, sheet_name="RMA_Loc")
        buffer.seek(0)
        st.download_button(
            label="📥 Tải kết quả Excel",
            data=buffer.getvalue(),
            file_name="RMA_Ketqua_Loc.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# === TAB 2: Trợ lý AI ===
if tab2:
    with tab2:
            st.header("🤖 Trợ lý AI – Hỏi đáp theo dữ liệu")
            question = st.text_area("✍️ Nhập câu hỏi:")
        
            df_ai = data_filtered.tail(max_rows)
        
            if st.button("🤖 Gửi câu hỏi"):
                if question.strip() == "":
                    st.warning("❗ Vui lòng nhập câu hỏi.")
                else:
                    with st.spinner("⏳ Đang truy vấn AI, vui lòng chờ..."):
                        # Tiến trình ảo
                        progress_placeholder = st.empty()
                        progress_bar = progress_placeholder.progress(0)
                        for percent_complete in range(100):
                            time.sleep(0.01)
                            progress_bar.progress(percent_complete + 1)
                        progress_placeholder.empty()
        
                        # Gọi AI
                        api_key = os.getenv("OPENAI_API_KEY")
                        ai_response, prompt_used = query_openai(
                            user_question=question,
                            df_summary=df_ai,
                            df_raw=df_raw,
                            api_key=api_key
                        )
        
                    # ✅ Hiện thông báo thành công rồi ẩn đi
                    success_box = st.empty()
                    success_box.success("✅ Đã xử lý xong câu hỏi.")
                    time.sleep(1)
                    success_box.empty()
        
                    # 📋 Hiển thị kết quả nếu có
                    if ai_response:
                        st.markdown("### 📋 Kết quả:")
                        st.markdown(ai_response, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Không có nội dung trả về từ AI hoặc intent.")
        
                    # 🔍 Hiển thị Debug nếu là admin
                    if st.session_state.get("debug_mode", False):
                        st.markdown("---")
                        st.markdown("### 🧠 Intent & Prompt Debug")
        
                        if prompt_used is not None:
                            st.markdown("#### 🧠 Intent hệ thống hiểu:")
                            st.code(prompt_used.get("intent", "Không rõ"), language="json")
        
                            st.markdown("#### 🧾 Prompt được gửi tới AI:")
                            st.code(prompt_used.get("prompt", ""), language="markdown")
                        else:
                            st.warning("⚠️ Không có dữ liệu về intent hoặc prompt được trả về.")
        
# === TAB 3: Truy vấn thống kê nhanh ===
with tab3:
    st.header("📋 Thống kê theo mẫu")

    # Bộ lọc khoảng thời gian
    col_date = find_col(data.columns, "ngày tiếp nhận")
    if col_date:
        data[col_date] = pd.to_datetime(data[col_date], errors='coerce')
        min_date = data[col_date].min()
        max_date = data[col_date].max()
        ngay_bat_dau, ngay_ket_thuc = st.date_input(
            "📅 Chọn khoảng ngày tiếp nhận:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        data = data[(data[col_date] >= pd.to_datetime(ngay_bat_dau)) &
                    (data[col_date] <= pd.to_datetime(ngay_ket_thuc))]

    # Bộ lọc nhóm hàng
    col_nhom = find_col(data.columns, "nhóm hàng")
    if col_nhom:
        nhom_list = data[col_nhom].dropna().unique().tolist()
        selected_nhoms = st.multiselect("📦 Chọn nhóm hàng cần phân tích:", nhom_list)
        if selected_nhoms:
            data = data[data[col_nhom].isin(selected_nhoms)]

    # Lấy quyền của người dùng từ session
    role = st.session_state.get("role", "guest")

    # Cập nhật danh sách truy vấn dựa trên quyền người dùng
    if role == "admin":
        options = [
            "— Chọn loại thống kê —",  # Dòng chọn loại thống kê
            "Tổng số sản phẩm tiếp nhận theo tháng/năm/quý",
            "Tỷ lệ sửa chữa thành công theo tháng/năm/quý",
            "Danh sách sản phẩm chưa sửa xong",
            "Top 10 khách hàng gửi nhiều nhất",
            "Top 10 sản phẩm bảo hành nhiều nhất",
            "Top lỗi phổ biến theo nhóm hàng",
            "Thời gian xử lý trung bình",
            "Top sản phẩm bảo hành nhiều trong nhóm hàng đã chọn",
            "Thời gian xử lý trung bình theo khách hàng",
            "Serial bị gửi nhiều lần",
            "Hiệu suất sửa chữa theo kỹ thuật viên",
            "Số lượng bảo hành theo sản phẩm",
            "Khách hàng gửi bảo hành bao nhiêu tính theo sản phẩm",
            "Sản phẩm nhận bảo hành bao nhiêu tính theo khách hàng"
        ]
    elif role == "mod":
        options = [
            "— Chọn loại thống kê —",  # Dòng chọn loại thống kê
            "Tổng số sản phẩm tiếp nhận theo tháng/năm/quý",
            "Top 10 khách hàng gửi nhiều nhất",
            "Top 10 sản phẩm bảo hành nhiều nhất",
            "Top lỗi phổ biến theo nhóm hàng",
            "Top sản phẩm bảo hành nhiều trong nhóm hàng đã chọn",
            "Serial bị gửi nhiều lần",
            "Hiệu suất sửa chữa theo kỹ thuật viên",
            "Số lượng bảo hành theo sản phẩm",
            "Khách hàng gửi bảo hành bao nhiêu tính theo sản phẩm",
            "Sản phẩm nhận bảo hành bao nhiêu tính theo khách hàng"
        ]
    else:  # user
        options = [
            "— Chọn loại thống kê —",  # Dòng chọn loại thống kê
            "Top lỗi phổ biến theo nhóm hàng",
            "Top sản phẩm bảo hành nhiều trong nhóm hàng đã chọn",
            "Số lượng bảo hành theo sản phẩm",
            "Khách hàng gửi bảo hành bao nhiêu tính theo sản phẩm",
            "Sản phẩm nhận bảo hành bao nhiêu tính theo khách hàng"
        ]


    # Hiển thị box và yêu cầu chọn
    selected = st.selectbox("📊 Chọn loại thống kê:", options, index=0)

    # Nếu chưa chọn, dừng lại
    if selected == "— Chọn loại thống kê —":
        st.warning("⚠️ Vui lòng chọn loại thống kê.")
        st.stop()

    if selected == "Tổng số sản phẩm tiếp nhận theo tháng/năm/quý":
        group_by = st.selectbox("Nhóm theo:", ["Năm", "Tháng", "Quý"])

        if group_by:
            with st.spinner("🔄 Đang truy vấn dữ liệu..."):
                time.sleep(1)
                title, df_out = rma_query_templates.query_1_total_by_group(data, group_by)

            if not df_out.empty:
                st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
                st.subheader(title)
                st.dataframe(df_out)
                export_excel_button(df_out, filename="tong_so_tiep_nhan.xlsx")
            else:
                st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Tỷ lệ sửa chữa thành công theo tháng/năm/quý":
        group_by = st.selectbox("Nhóm theo:", ["Năm", "Tháng", "Quý"])

        if group_by:
            with st.spinner("🔄 Đang truy vấn dữ liệu..."):
                time.sleep(1)
                title, df_out = rma_query_templates.query_2_success_rate_by_group(data, group_by)

            if not df_out.empty:
                st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
                st.subheader(title)
                st.dataframe(df_out)
                export_excel_button(df_out, filename="ti_le_sua_chua.xlsx")
            else:
                st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Danh sách sản phẩm chưa sửa xong":
        with st.spinner("🔄 Đang truy vấn dữ liệu..."):
            time.sleep(1)
            title, df_out = rma_query_templates.query_3_unrepaired_products(data)

        if not df_out.empty:
            st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
            st.subheader(title)
            st.dataframe(df_out)
            export_excel_button(df_out, filename="chua_sua_xong.xlsx")
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Top 10 khách hàng gửi nhiều nhất":
        with st.spinner("🔄 Đang truy vấn dữ liệu..."):
            time.sleep(1)
            title, df_out = rma_query_templates.query_4_top_customers(data)

        if not df_out.empty:
            st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
            st.subheader(title)
            st.dataframe(df_out)
            export_excel_button(df_out, filename="top_khach_hang.xlsx")
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")


    elif selected == "Top 10 sản phẩm bảo hành nhiều nhất":
        with st.spinner("🔄 Đang truy vấn dữ liệu..."):
            time.sleep(1)
            title, df_out = rma_query_templates.query_7_top_products(data)

        if not df_out.empty:
            st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
            st.subheader(title)
            st.dataframe(df_out)
            export_excel_button(df_out, filename="top_san_pham.xlsx")
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Top lỗi phổ biến theo nhóm hàng":
        with st.spinner("🔄 Đang truy vấn dữ liệu..."):
            time.sleep(1)
            title, df_out = rma_query_templates.query_top_errors(data)

        if not df_out.empty:
            st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
            st.subheader(title)
            fig = px.bar(df_out, x="Lỗi", y="Số lần gặp", title="Biểu đồ lỗi kỹ thuật phổ biến",
                         text_auto=True, template="plotly_dark")
            fig.update_layout(xaxis_tickangle=-45, height=500, margin=dict(l=30, r=30, t=60, b=150))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_out)
            export_excel_button(df_out, filename="top_loi_pop.xlsx")
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Thời gian xử lý trung bình":
        with st.spinner("🔄 Đang truy vấn dữ liệu..."):
            time.sleep(1)
            title, df_out = rma_query_templates.query_avg_processing_time(data)

        if not df_out.empty:
            st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
            st.subheader(title)
            st.dataframe(df_out)
            export_excel_button(df_out, filename="thoi_gian_xu_ly_tb.xlsx")
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")


    elif selected == "Top sản phẩm bảo hành nhiều trong nhóm hàng đã chọn":
        if selected_nhoms and len(selected_nhoms) == 1:
            selected_group = selected_nhoms[0]  # lấy nhóm duy nhất
            with st.spinner("🔄 Đang truy vấn dữ liệu..."):
                time.sleep(1)
                title, df_out = rma_query_templates.query_top_products_in_group(data, selected_group)

            if not df_out.empty:
                st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
                st.subheader(title)
                st.dataframe(df_out)
                export_excel_button(df_out, filename=f"top_san_pham_{selected_group}.xlsx")
            else:
                st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")
        elif len(selected_nhoms) > 1:
            st.warning("⚠️ Truy vấn này chỉ hỗ trợ khi chọn đúng 1 nhóm hàng.")
        else:
            st.warning("⚠️ Vui lòng chọn nhóm hàng cần phân tích.")



    elif selected == "Thời gian xử lý trung bình theo khách hàng":
        col_khach = find_col(data.columns, "tên khách hàng")
        if col_khach:
            unique_khach = data[col_khach].dropna().unique().tolist()
            selected_khach = st.selectbox("🔍 Chọn khách hàng cần xem:", unique_khach)
        else:
            selected_khach = None

        if selected_khach:
            with st.spinner("🔄 Đang truy vấn dữ liệu..."):
                time.sleep(1)
                title, df_out = rma_query_templates.query_avg_time_by_customer(data, selected_khach)

            if not df_out.empty:
                st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
                st.subheader(title)
                st.dataframe(df_out)
                export_excel_button(df_out, filename="tg_xu_ly_theo_khach.xlsx")
            else:
                st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Serial bị gửi nhiều lần":
        with st.spinner("🔄 Đang truy vấn dữ liệu..."):
            time.sleep(1)
            title, df_out = rma_query_templates.query_serial_lap_lai(data)

        if not df_out.empty:
            st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
            st.subheader(title)
            st.dataframe(df_out)
            export_excel_button(df_out, filename="serial_lap_lai.xlsx")
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Hiệu suất sửa chữa theo kỹ thuật viên":
        with st.spinner("🔄 Đang truy vấn dữ liệu..."):
            time.sleep(1)
            title, df_out = rma_query_templates.query_21_technician_status_summary(data)

        if not df_out.empty:
            st.toast("✅ Đã xử lý xong truy vấn!", icon="🎉")
            st.subheader(title)
            st.dataframe(df_out)
            export_excel_button(df_out, filename="hieu_suat_ktv.xlsx")
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu phù hợp.")

    elif selected == "Khách hàng gửi bảo hành bao nhiêu tính theo sản phẩm":
        col_san_pham = find_col(data.columns, "sản phẩm")
        if col_san_pham:
            unique_products = data[col_san_pham].dropna().unique().tolist()
            selected_product = st.selectbox("📦 Chọn sản phẩm", sorted(unique_products))

            if selected_product:
                # 🌟 Hiệu ứng loading
                with st.spinner("🔍 Đang truy vấn dữ liệu, vui lòng chờ..."):
                    time.sleep(1)  # giả lập độ trễ
                    title, df_out = rma_query_templates.query_16_top_customers_by_product(data, selected_product)

                # ✅ Thông báo hoàn tất (hiện tạm)
                st.toast("✅ Đã xử lý xong truy vấn.", icon="🎉")

                # 📊 Hiển thị kết quả
                st.subheader(title)
                st.dataframe(df_out)
                export_excel_button(df_out, filename=f"top_khach_{selected_product}.xlsx")
        else:
            st.error("❌ Không tìm thấy cột tên sản phẩm trong dữ liệu.")

    elif selected == "Sản phẩm nhận bảo hành bao nhiêu tính theo khách hàng":
        col_khach = find_col(data.columns, "tên khách hàng")
        col_san_pham = find_col(data.columns, "sản phẩm")

        if col_khach and col_san_pham:
            unique_khach = data[col_khach].dropna().unique().tolist()
            selected_khach = st.selectbox("👤 Chọn khách hàng", sorted(unique_khach))

            if selected_khach:
                with st.spinner("🔄 Đang truy vấn dữ liệu, vui lòng chờ..."):
                    time.sleep(1)
                    title, df_out = rma_query_templates.query_5_top_products_by_customer(
                        data, selected_khach, top_n=30
                    )

                st.toast("✅ Đã xử lý xong truy vấn.", icon="📊")
                st.subheader(title)
                st.dataframe(df_out)
                export_excel_button(df_out, filename=f"top_san_pham_{selected_khach}.xlsx")
        else:
            st.error("❌ Không tìm thấy cột 'tên khách hàng' hoặc 'sản phẩm' trong dữ liệu.")
         
    elif selected == "Số lượng bảo hành theo sản phẩm":
        col_sp = find_col(data.columns, "sản phẩm")
        ok_col = find_col(data.columns, "đã sửa xong")  # Cột "Đã sửa xong"
        if col_sp and ok_col:
            unique_products = sorted(data[col_sp].dropna().unique().tolist())
            selected_product = st.selectbox("🧱 Chọn sản phẩm cần thống kê:", unique_products)

            if selected_product:
                with st.spinner("🔄 Đang truy vấn dữ liệu..."):
                    time.sleep(1)
                    # Đếm số lượt gửi và số lượng đã sửa xong
                    count = data[data[col_sp] == selected_product].shape[0]
                    fixed = data[data[col_sp] == selected_product][ok_col].sum()
                    ratio = round(fixed / count * 100, 1) if count else 0

                    # Tạo bảng kết quả
                    df_out = pd.DataFrame({
                        "Sản phẩm": [selected_product],
                        "Số lượt gửi": [count],
                        "Đã sửa xong": [fixed],
                        "Tỷ lệ sửa thành công (%)": [ratio]
                    })

                st.toast("✅ Đã xử lý xong truy vấn!", icon="📦")
                st.subheader(f"Kết quả cho sản phẩm: {selected_product}")
                st.dataframe(df_out)
                export_excel_button(df_out, filename=f"bao_hanh_{selected_product}.xlsx")
            else:
                st.warning("⚠️ Vui lòng chọn sản phẩm cần thống kê.")
        else:
            st.error("❌ Không tìm thấy cột sản phẩm hoặc cột 'Đã sửa xong' trong dữ liệu.")

