
import pandas as pd
from openai import OpenAI

def chuan_hoa_ten_cot(df):
    import unicodedata, re
    def normalize(text):
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        text = re.sub(r"[^\w\s]", "", text)
        text = text.lower().strip().replace(" ", "_")
        return text
    return df.rename(columns={col: normalize(col) for col in df.columns})

def prepare_prompt(user_question, df_summary, matched_names=None):
    if len(df_summary) > 100:
        df_summary = df_summary.head(100)
    df_summary = chuan_hoa_ten_cot(df_summary.copy())
    if "ngay_nhan" in df_summary.columns:
        df_summary["ngay_nhan"] = pd.to_datetime(df_summary["ngay_nhan"], errors="coerce")
        df_summary["nam"] = df_summary["ngay_nhan"].dt.year
        df_summary["thang"] = df_summary["ngay_nhan"].dt.month
        df_summary["quy"] = df_summary["ngay_nhan"].dt.quarter

    csv_data = df_summary.to_csv(index=False)
    extra_info = ""
    if matched_names:
        extra_info = f"(Đã dò gần đúng tên khách hàng: {matched_names})\n"
    prompt = f"""{extra_info}
Dưới đây là bảng dữ liệu bảo hành (dưới dạng csv). Hãy phân tích và trả lời câu hỏi bên dưới, có số liệu cụ thể, ngắn gọn và dễ hiểu.
Dữ liệu:
{csv_data}

Câu hỏi: {user_question}
"""
    return prompt

def query_openai(user_question, df_summary, df_raw, api_key, model="gpt-3.5-turbo", matched_names=None):
    if df_summary.empty:
        return "Không có dữ liệu phù hợp để trả lời.", {
            "intent": "no_data",
            "prompt": ""
        }

    from intent_handler import handle_intent
    df_result, intent_response, detected_intent = handle_intent(user_question, df_raw)

    if detected_intent != "unknown":
        return intent_response, {
            "intent": detected_intent,
            "prompt": "(Trả lời bằng intent, không dùng AI)"
        }

    # Dùng OpenAI nếu không xác định intent
    from openai import OpenAI
    prompt = prepare_prompt(user_question, df_summary, matched_names)

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là một trợ lý dữ liệu chuyên về phân tích bảo hành RMA. Trả lời ngắn gọn, dễ hiểu, bằng tiếng Việt, có số liệu cụ thể."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip(), {
            "intent": "chat_completion",
            "prompt": prompt
        }
    except Exception as e:
        return f"Lỗi khi gọi OpenAI: {e}", {
            "intent": "error",
            "prompt": str(e)
        }
