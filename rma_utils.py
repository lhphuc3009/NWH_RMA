import pandas as pd

COLUMN_MAPPING = {
    "Tên khách hàng": [
        "khach hang",
        "ten khach",
        "ten kh",
        "cty",
        "cong ty",
        "ten cong ty"
    ],
    "Sản phẩm": [
        "san pham",
        "ma san pham",
        "ma hang",
        "product",
        "ten sp"
    ],
    "Nhóm hàng": [
        "nhom hang",
        "loai hang",
        "danh muc",
        "category"
    ],
    "Kỹ thuật viên": [
        "ky thuat vien",
        "ktv",
        "nhan vien sua",
        "nguoi sua",
        "sua chua"
    ],
    "Đã sửa xong": [
        "da sua",
        "da sua xong",
        "hoan tat",
        "xong",
        "done",
        "fix ok"
    ],
    "Không sửa được": [
        "khong sua",
        "khong sua duoc",
        "that bai",
        "fail",
        "khong thanh cong"
    ],
    "Từ chối bảo hành": [
        "tu choi",
        "khong bh",
        "tu choi bh",
        "bao hanh tu choi"
    ],
    "Tên lỗi": [
        "ten loi",
        "loi",
        "mo ta loi",
        "loi ky thuat",
        "error"
    ],
    "Ngày tiếp nhận": [
        "ngay nhan",
        "ngay tiep nhan",
        "thoi gian nhan",
        "ngay bao hanh",
        "ngay gui"
    ],
    "Năm": [
        "nam",
        "year"
    ],
    "Tháng": [
        "thang",
        "month"
    ],
    "Quý": [
        "quy",
        "quarter"
    ],
    "Nguồn file": [
        "nguon file",
        "file name",
        "ten file",
        "nguon"
    ]
}

import unicodedata
import re

def clean_text(text):
    if not isinstance(text, str): return ""
    text = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    text = text.replace('đ', 'd').replace('Đ', 'd')
    text = text.lower().strip()
    text = re.sub(r'[\W_]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def normalize_for_match(text):
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    text = re.sub(r'[\-_\&]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def match_block(name, keyword):
    n_name = normalize_for_match(name)
    n_key = normalize_for_match(keyword)
    n_name_words = n_name.split()
    n_key_words = n_key.split()
    for i in range(len(n_name_words) - len(n_key_words) + 1):
        if n_name_words[i:i+len(n_key_words)] == n_key_words:
            return True
    return False

def find_col(cols, keyword, column_mapping={}):
    keyword_clean = clean_text(keyword)
    mapping_found = column_mapping.get(keyword.strip(), [])

    for alias in mapping_found:
        for col in cols:
            if clean_text(col) == clean_text(alias):
                return col

    for col in cols:
        if keyword_clean == clean_text(col):
            return col
    for col in cols:
        if keyword_clean in clean_text(col):
            return col
    return None

def ensure_time_columns(df):
    date_col = None
    for col in df.columns:
        cleaned = unicodedata.normalize('NFKD', col).lower().replace('đ','d')
        cleaned = re.sub(r'[\W_]+', ' ', cleaned)
        if ("ngay" in cleaned) and (("nhan" in cleaned) or ("tiep" in cleaned)):
            date_col = col
            break
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df["Năm"] = df[date_col].dt.year
        df["Tháng"] = df[date_col].dt.month
        df["Quý"] = df[date_col].dt.quarter
    return df

def extract_time_filter_from_question(question):
    years = re.findall(r"(20\d{2})", question)
    years = [int(y) for y in years]
    months = re.findall(r"tháng\s*(\d{1,2})", question)
    months = [int(m) for m in months if 0 < int(m) <= 12]
    quarters = re.findall(r"quý\s*([1234IiVv]+)", question)
    quarter_map = {
        "1": 1, "I": 1, "i": 1,
        "2": 2, "II": 2, "ii": 2,
        "3": 3, "III": 3, "iii": 3,
        "4": 4, "IV": 4, "iv": 4,
    }
    q_norm = []
    for q in quarters:
        qv = str(q).upper()
        if qv in quarter_map:
            q_norm.append(quarter_map[qv])
        else:
            try:
                q_norm.append(int(qv))
            except:
                pass
    quarters = [q for q in q_norm if 1 <= q <= 4]
    return years, months, quarters

def filter_df_by_time(df, years=None, months=None, quarters=None):
    df2 = df.copy()
    if years and "Năm" in df2.columns:
        df2 = df2[df2["Năm"].isin(years)]
    if months and "Tháng" in df2.columns:
        df2 = df2[df2["Tháng"].isin(months)]
    if quarters and "Quý" in df2.columns:
        df2 = df2[df2["Quý"].isin(quarters)]
    return df2
import streamlit as st

def bo_loc_da_nang(df, prefix_key=""):
    df_filtered = df.copy()
    
    with st.sidebar.expander("📕 Bộ lọc nâng cao", expanded=False):
        col1, col2 = st.columns(2)
        years = sorted(df["Năm"].dropna().unique())
        months = sorted(df["Tháng"].dropna().unique())
        selected_years = col1.multiselect("Năm", years, key=prefix_key + "_loc_nam")
        selected_months = col2.multiselect("Tháng", months, key=prefix_key + "_loc_thang")

        col3, col4 = st.columns(2)
        quarters = sorted(df["Quý"].dropna().unique())
        selected_quarters = col3.multiselect("Quý", quarters, key=prefix_key + "_loc_quy")
        date_range = col4.date_input("Ngày tiếp nhận (Từ – Đến)", [], key=prefix_key + "_loc_ngay")

        if selected_years:
            df_filtered = df_filtered[df_filtered["Năm"].isin(selected_years)]
        if selected_months:
            df_filtered = df_filtered[df_filtered["Tháng"].isin(selected_months)]
        if selected_quarters:
            df_filtered = df_filtered[df_filtered["Quý"].isin(selected_quarters)]
        if isinstance(date_range, list) and len(date_range) == 2:
            col_date = find_col(df.columns, "ngày tiếp nhận")
            if col_date:
                df_filtered = df_filtered[
                    (df_filtered[col_date] >= pd.to_datetime(date_range[0])) &
                    (df_filtered[col_date] <= pd.to_datetime(date_range[1]))
                ]

    return df_filtered

def render_result_table(results):
    """
    Nhận vào danh sách [("Tên sản phẩm", lượt gửi), ...] và trả HTML bảng
    """
    html = "<table border='1' cellpadding='6' cellspacing='0' style='width:100%; border-collapse: collapse; background-color: #1e1e1e; color: white;'>"
    html += "<tr style='background-color: #333;'><th>STT</th><th>Sản phẩm</th><th>Lượt gửi</th></tr>"
    for i, (product, count) in enumerate(results, 1):
        html += f"<tr><td>{i}</td><td>{product}</td><td>{count}</td></tr>"
    html += "</table>"
    return html

def render_bo_loc_sidebar(df, prefix_key=""):
    with st.expander("📕 Bộ lọc nâng cao", expanded=False):
        col1, col2 = st.columns(2)
        years = sorted(df["Năm"].dropna().unique())
        months = sorted(df["Tháng"].dropna().unique())
        selected_years = col1.multiselect("Năm", years, key=prefix_key + "_loc_nam")
        selected_months = col2.multiselect("Tháng", months, key=prefix_key + "_loc_thang")

        col3, col4 = st.columns(2)
        quarters = sorted(df["Quý"].dropna().unique())
        selected_quarters = col3.multiselect("Quý", quarters, key=prefix_key + "_loc_quy")
        date_range = col4.date_input("Ngày tiếp nhận (Từ – Đến)", [], key=prefix_key + "_loc_ngay")

        return {
            "years": selected_years,
            "months": selected_months,
            "quarters": selected_quarters,
            "date_range": date_range
        }

def apply_bo_loc(df, filters):
    df_filtered = df.copy()

    if filters["years"]:
        df_filtered = df_filtered[df_filtered["Năm"].isin(filters["years"])]
    if filters["months"]:
        df_filtered = df_filtered[df_filtered["Tháng"].isin(filters["months"])]
    if filters["quarters"]:
        df_filtered = df_filtered[df_filtered["Quý"].isin(filters["quarters"])]
    if isinstance(filters["date_range"], list) and len(filters["date_range"]) == 2:
        col_date = find_col(df.columns, "ngày tiếp nhận")
        if col_date:
            df_filtered = df_filtered[
                (df_filtered[col_date] >= pd.to_datetime(filters["date_range"][0])) &
                (df_filtered[col_date] <= pd.to_datetime(filters["date_range"][1]))
            ]
    return df_filtered
