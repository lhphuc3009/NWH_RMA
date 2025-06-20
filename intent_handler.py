import re
import pandas as pd
from rma_utils import render_result_table

def normalize_text(text):
    text = text.lower()
    text = text.replace("gởi", "gửi")
    text = text.replace("bảo hành", "gửi")
    text = text.replace("nhận", "gửi")
    return text

def extract_time_from_question(question):
    month_match = re.search(r"tháng\s*(\d{1,2})", question, re.IGNORECASE)
    quarter_match = re.search(r"quý\s*(\d)", question, re.IGNORECASE)
    year_match = re.search(r"năm\s*(\d{4})", question, re.IGNORECASE)

    month = int(month_match.group(1)) if month_match else None
    quarter = int(quarter_match.group(1)) if quarter_match else None
    year = int(year_match.group(1)) if year_match else None

    return year, month, quarter

def extract_customer_from_question(question):
    q = normalize_text(question)
    if "ktv" in q or "kỹ thuật viên" in q:
        return None
    match = re.search(r"khách hàng ([\w\s\-\.]+?) gửi", q)
    if not match:
        match = re.search(r"([\w\s\-\.]+?) gửi", q)
    return match.group(1).strip() if match else None

def extract_product_from_question(question):
    match = re.search(r"gửi (?:sản phẩm\s)?(.+?) (?:nhiều|trong|ở|vào|\?|$)", question, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def recognize_intent(question):
    q = normalize_text(question)
    if re.search(r"sản phẩm (gì|nào)? ?nhiều nhất", q):
        return {"intent": "top_product", "params": {"question": question}}
    if re.search(r"sản phẩm (gì|nào).*nhiều", q):
        return {"intent": "top_products", "params": {"question": question}}
    if "khách" in q and "gửi nhiều" in q:
        return {"intent": "top_customers", "params": {"question": question}}
    if re.search(r"sản phẩm gì nhiều", q):
        return {"intent": "top_products", "params": {"question": question}}
    if re.search(r"(cái gì|loại gì|mặt hàng gì|loại nào|cái nào).*?(hư|lỗi|gửi).*?(nhiều|nhất)?", q):
        return {"intent": "top_products", "params": {"question": question}}
    if "sản phẩm" in q and ("lỗi nhiều" in q or "gửi nhiều" in q or "nhiều nhất" in q):
        return {"intent": "top_products", "params": {"question": question}}
    if re.search(r"gửi gì nhiều", q):
        customer = extract_customer_from_question(question)
        return {"intent": "top_products_by_customer", "params": {"question": question, "customer": customer}}
    if re.search(r"(ai|khách|khách hàng).*gửi.*sản phẩm", q) and ("nhiều" in q or "top" in q):
        product = extract_product_from_question(question)
        if product:
            return {"intent": "top_customers_by_product", "params": {"question": question, "product": product}}
    if "ktv" in q or "kỹ thuật viên" in q:
        return {"intent": "top_ktv", "params": {}}
    if ("gửi" in q or "đã gửi" in q) and "sản phẩm" in q and ("tháng" in q or "quý" in q or "năm" in q):
        if "khách hàng" in q or re.search(r"^\s*\w+.*gửi", q):
            customer = extract_customer_from_question(question)
            return {"intent": "count_product_by_customer", "params": {"question": question, "customer": customer}}
        return {"intent": "count_product", "params": {"question": question}}
    return {"intent": "unknown", "params": {}}

def filter_by_time(df, question):
    year, month, quarter = extract_time_from_question(question)
    df_filtered = df.copy()
    if year and "nam" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["nam"] == year]
    if month and "thang" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["thang"] == month]
    if quarter and "quy" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["quy"] == quarter]
    return df_filtered

def handle_top_products(df, params):
    question = params.get("question", "")
    df_filtered = filter_by_time(df, question)
    for col in ["san_pham", "model", "ten_san_pham"]:
        if col in df_filtered.columns:
            top_df = df_filtered[col].value_counts().head(10).reset_index()
            top_df.columns = ["san_pham", "so_luong"]
    result_list = list(top_df.itertuples(index=False, name=None))
    return df_filtered, render_result_table(result_list)

def handle_top_ktv(df, question):
    df_filtered = filter_by_time(df, question)
    for col in ["ktv", "ten_ky_thuat_vien"]:
        if col in df_filtered.columns:
            top = df_filtered[col].value_counts().idxmax()
            count = df_filtered[col].value_counts().max()
            return df_filtered[df_filtered[col] == top], f"Kỹ thuật viên xử lý nhiều nhất là **{top}** với tổng cộng {count} lượt xử lý."
    return df_filtered, "Không tìm thấy dữ liệu kỹ thuật viên trong bảng."

def handle_count_product(df, params):
    question = params.get("question", "")
    year, month, quarter = extract_time_from_question(question)
    df_filtered = filter_by_time(df, question)
    total = len(df_filtered)

    result = {
        "year": year,
        "month": month,
        "quarter": quarter,
        "total": total
    }

    return result

def handle_count_product_by_customer(df, params):
    customer = params.get("customer")
    question = params.get("question", "")
    df_filtered = filter_by_time(df, question)
    for col in ["ten_khach_hang", "khach_hang"]:
        if col in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[col].str.contains(customer, case=False, na=False)]
            break
    total = len(df_filtered)
    return df_filtered, f"Khách hàng **{customer}** đã gửi tổng cộng {total} sản phẩm theo yêu cầu lọc thời gian."

def handle_top_customers(df, params):
    question = params.get("question", "")
    df_filtered = filter_by_time(df, question)
    for col in ["ten_khach_hang", "khach_hang"]:
        if col in df_filtered.columns:
            top_df = df_filtered[col].value_counts().head(10).reset_index()
            top_df.columns = ["khach_hang", "so_luong"]
    result_list = list(top_df.itertuples(index=False, name=None))
    return df_filtered, render_result_table(result_list)
    
def handle_top_products_by_customer(df, params):
    customer = params.get("customer")
    question = params.get("question", "")
    df_filtered = filter_by_time(df, question)

    for col in ["ten_khach_hang", "khach_hang"]:
        if col in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[col].str.contains(customer, case=False, na=False)]
            break

    for col in ["san_pham", "model", "ten_san_pham"]:
        if col in df_filtered.columns:
            top_df = df_filtered[col].value_counts().head(10).reset_index()
            top_df.columns = ["san_pham", "so_luong"]
    result_list = list(top_df.itertuples(index=False, name=None))
    return df_filtered, render_result_table(result_list)
 
def handle_intent(question, df):
    intent_info = recognize_intent(question)
    intent = intent_info["intent"]
    params = intent_info.get("params", {})

    if intent == "top_customers":
        return handle_top_customers(df, params) + (intent,)
    elif intent in ["top_product", "top_products"]:
        return handle_top_products(df, params) + (intent,)
    elif intent == "top_products_by_customer":
        return handle_top_products_by_customer(df, params) + (intent,)
    elif intent == "top_customers_by_product":
        return handle_top_customers_by_product(df, params) + (intent,)
    elif intent == "top_ktv":
        return handle_top_ktv(df, question) + (intent,)
    elif intent == "count_product":
        result = handle_count_product(df, params)
        month = result.get("month")
        year = result.get("year")
        total = result.get("total")
        if month and year and total is not None:
            return df[df["thang"] == month], f"Trong tháng {month} năm {year}, đã có tổng cộng {total} sản phẩm được nhận bảo hành.", intent
        elif year and total is not None:
            return df[df["nam"] == year], f"Trong năm {year}, đã có tổng cộng {total} sản phẩm được nhận bảo hành.", intent
        else:
            return df, f"Đã có tổng cộng {total} sản phẩm được nhận bảo hành.", intent
    elif intent == "count_product_by_customer":
        return handle_count_product_by_customer(df, params) + (intent,)
    else:
        return df, "Không xác định được ý định từ câu hỏi.", "unknown"
