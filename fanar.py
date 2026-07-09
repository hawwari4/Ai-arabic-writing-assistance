import os
import re
import json
import logging
import datetime
import tempfile  # <-- ADD THIS IMPORT
from typing import Optional, Any, List
import requests

API_KEY = os.environ.get("FANAR_API_KEY", "YOUR_API_KEY")
BASE_URL = "https://api.fanar.qa"
MODEL_NAME = "Fanar"

# ---------------------------------------------------------------------------
# LOGGING (FIXED: Moved to System Temp Folder)
# ---------------------------------------------------------------------------
# By using tempfile.gettempdir(), logs go to your OS's hidden temp folder 
# (e.g., C:\Users\You\AppData\Local\Temp\fanar_logs on Windows). 
# VS Code Live Server will NEVER see these files, so it won't refresh your page!
LOG_DIR = os.path.join(tempfile.gettempdir(), "fanar_logs")
os.makedirs(LOG_DIR, exist_ok=True)
RAW_LOG_PATH = os.path.abspath(os.path.join(LOG_DIR, "fanar_raw.log"))

logger = logging.getLogger("fanar")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s [fanar]: %(message)s"))
    logger.addHandler(ch)
    # File handler (now safely in the temp folder)
    fh = logging.FileHandler(os.path.join(LOG_DIR, "fanar_app.log"), encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s [fanar]: %(message)s"))
    logger.addHandler(fh)

def _log_raw_response(raw_text: str, ok: bool) -> None:
    try:
        with open(RAW_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.datetime.now().isoformat()} | ok={ok} =====\n")
            f.write(raw_text)
            f.write("\n")
    except Exception as e:
        logger.error(f"Failed to write raw log: {e}")

# ---------------------------------------------------------------------------
# FANAR CLIENT
# ---------------------------------------------------------------------------
class FanarClient:
    def __init__(self, model: str = MODEL_NAME, api_key: str = API_KEY, max_output_tokens: int = 2048):
        self.model = model
        self.api_key = api_key
        self.max_output_tokens = max_output_tokens

    def chat(self, messages: List[dict], temperature: float = 0.1) -> str:
        if not self.api_key or self.api_key == "YOUR_API_KEY":
            raise RuntimeError("FANAR_API_KEY غير مضبوط في متغيرات البيئة.")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_output_tokens,
            "temperature": temperature,
        }
        
        logger.info(f"Sending request to Fanar API | model={self.model} | messages_count={len(messages)}")
        try:
            resp = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            finish_reason = body["choices"][0].get("finish_reason")
            logger.info(f"Received response from Fanar | finish_reason={finish_reason} | content_length={len(content)}")
            if finish_reason == "length":
                logger.warning("Fanar response was cut off (finish_reason=length).")
            return content
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_SCORES = """أنت معلّم لغة عربية خبير في تقييم مهارة التعبير الكتابي لدى طلاب المرحلة الإعدادية.
تُعطى لك بيانات المهمة الكتابية ومقال الطالب. قيّم المقال وفق معايير التقييم المرفقة فقط،
وأعطِ لكل معيار درجة من 1 إلى 3 (1: غير متوافر، 2: متوافر إلى حد ما، 3: متوافر بشكل كبير).
كل تعليق جملة واحدة قصيرة (10 كلمات كحد أقصى)، بلا علامات اقتباس " داخل النص.
أعد الإجابة بصيغة JSON صِرف فقط، دون أي مقدمة أو شرح أو علامات ```json. ابدأ بـ { وانتهِ بـ }."""

SYSTEM_PROMPT_WRITING = """أنت معلّم لغة عربية خبير في تصحيح الأخطاء الإملائية والنحوية لطلاب المرحلة الإعدادية.
تُعطى لك مقال الطالب. استخرج بحد أقصى 4 أخطاء فعلية (الأبرز فقط)، واكتب فقرة واحدة محسّنة من المقال،
وتعليقًا عامًا مشجعًا (15 كلمة كحد أقصى). بلا علامات اقتباس " داخل قيم النصوص.
أعد الإجابة بصيغة JSON صِرف فقط، دون أي مقدمة أو شرح أو علامات ```json. ابدأ بـ { وانتهِ بـ }."""

def build_scores_messages(task: dict, essay: str) -> List[dict]:
    criteria_lines = "\n".join(f"- {c}" for c in task["rubric"])
    schema_scores = ",\n".join(f'    "{c}": 2' for c in task["rubric"])
    schema_feedback = ",\n".join(f'    "{c}": "تعليق قصير"' for c in task["rubric"])
    
    user_prompt = f"""## بيانات المهمة
النص:
{task['text']}

التخطيط للكتابة:
{task['planning']}

الإرشادات:
{task['guidelines']}

معايير التقييم:
{criteria_lines}

## مقال الطالب
{essay}

## صيغة الإجابة (JSON فقط، بهذا الشكل)
{{
  "scores": {{
{schema_scores}
  }},
  "feedback": {{
{schema_feedback}
  }}
}}"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_SCORES},
        {"role": "user", "content": user_prompt}
    ]

def build_writing_messages(task: dict, essay: str) -> List[dict]:
    user_prompt = f"""## مقال الطالب
{essay}

## صيغة الإجابة (JSON فقط، بهذا الشكل)
{{
  "mistakes": [
    {{"type": "إملائي أو نحوي", "original": "...", "correction": "...", "explanation": "..."}}
  ],
  "improved_paragraph": "...",
  "overall_comment": "..."
}}"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_WRITING},
        {"role": "user", "content": user_prompt}
    ]

# ---------------------------------------------------------------------------
# JSON PARSING & VALIDATION
# ---------------------------------------------------------------------------
def _autofix_json(json_str: str, max_attempts: int = 10) -> Optional[dict]:
    text = json_str
    seen_states = set()
    for _ in range(max_attempts):
        if text in seen_states:
            break
        seen_states.add(text)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            if "Expecting ',' delimiter" in e.msg:
                text = text[:e.pos] + "," + text[e.pos:]
            elif "Expecting property name enclosed in double quotes" in e.msg:
                before = text[:e.pos].rstrip()
                if before.endswith(","):
                    text = before[:-1] + text[e.pos:]
                else:
                    match = re.search(r'([a-zA-Z\u0600-\u06FF_]+)\s*:', text[max(0, e.pos-50):e.pos+10])
                    if match:
                        key = match.group(1)
                        start_idx = text.rfind(key, max(0, e.pos-50), e.pos)
                        if start_idx != -1:
                            text = text[:start_idx] + f'"{key}"' + text[start_idx+len(key):]
                    else:
                        break
            elif "Extra data" in e.msg:
                text = text[:e.pos]
            elif "Expecting value" in e.msg:
                before = text[:e.pos].rstrip()
                if before.endswith(","):
                    text = before[:-1] + text[e.pos:]
                else:
                    break
            else:
                break
    return None

def extract_json(raw_text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*|```", "", raw_text.strip()).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    json_str = match.group(0) if match else cleaned
    
    try:
        data = json.loads(json_str)
        _log_raw_response(raw_text, ok=True)
        return data
    except json.JSONDecodeError as e:
        fixed = _autofix_json(json_str)
        if fixed is not None:
            _log_raw_response(raw_text, ok=True)
            logger.warning("Auto-repaired malformed JSON from the model.")
            return fixed
        
        _log_raw_response(raw_text, ok=False)
        logger.error(f"JSON parse failed: {e}")
        raise ValueError(f"رد النموذج ليس JSON صالحًا: {e.msg}")

def normalize_result(data: dict, task: dict) -> dict:
    data.setdefault("scores", {})
    data.setdefault("feedback", {})
    data.setdefault("mistakes", [])
    data.setdefault("improved_paragraph", "")
    data.setdefault("overall_comment", "")

    for criterion in task["rubric"]:
        if criterion not in data["scores"] or not isinstance(data["scores"][criterion], (int, float)):
            data["scores"][criterion] = 0
            logger.warning(f"Missing/invalid score for criterion '{criterion}', defaulted to 0.")
        if criterion not in data["feedback"]:
            data["feedback"][criterion] = "لم يتوفر تعليق لهذا المعيار في رد النموذج."

    cleaned_mistakes = []
    for m in data["mistakes"]:
        if not isinstance(m, dict):
            continue
        cleaned_mistakes.append({
            "type": m.get("type", "نحوي"),
            "original": m.get("original", ""),
            "correction": m.get("correction", ""),
            "explanation": m.get("explanation", ""),
        })
    data["mistakes"] = cleaned_mistakes

    if not data["overall_comment"]:
        data["overall_comment"] = "تعذّر الحصول على تعليق عام كامل من النموذج، لكن التقييم أعلاه متاح."

    return data

def evaluate_essay(task: dict, essay: str) -> dict:
    logger.info(f"Evaluating task='{task.get('id', '?')}' essay_len={len(essay)} rubric_items={len(task['rubric'])}")
    client = FanarClient()

    scores_messages = build_scores_messages(task, essay)
    scores_raw = client.chat(scores_messages)
    scores_data = extract_json(scores_raw)

    result = {
        "scores": scores_data.get("scores", {}),
        "feedback": scores_data.get("feedback", {}),
        "mistakes": [],
        "improved_paragraph": "",
        "overall_comment": "",
    }

    try:
        writing_messages = build_writing_messages(task, essay)
        writing_raw = client.chat(writing_messages)
        writing_data = extract_json(writing_raw)
        result["mistakes"] = writing_data.get("mistakes", [])
        result["improved_paragraph"] = writing_data.get("improved_paragraph", "")
        result["overall_comment"] = writing_data.get("overall_comment", "")
    except Exception as e:
        logger.error(f"Mistakes/rewrite call failed, showing scores only: {e}")

    return normalize_result(result, task)

if __name__ == "__main__":
    sample_task = {
        "text": "حكم ممارسة الألعاب الإلكترونية بين الشباب",
        "planning": "مقدمة، عرض، خاتمة",
        "guidelines": "اذكر رأيك مدعمًا بحجة",
        "rubric": ["إبداء الرأي الشخصي", "قوة الحجج"],
    }
    sample_essay = "الألعاب الإلكترونية مفيدة لأنها تنمي التفكير والتركيز."
    print(evaluate_essay(sample_task, sample_essay))