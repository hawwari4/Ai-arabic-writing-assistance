import os
import re
import json
import logging
import datetime
import tempfile
from typing import Optional, Any, List
import requests

API_KEY = os.environ.get("FANAR_API_KEY", "YOUR_API_KEY")
BASE_URL = "https://api.fanar.qa"
MODEL_NAME = "Fanar"

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(tempfile.gettempdir(), "fanar_logs")
os.makedirs(LOG_DIR, exist_ok=True)
RAW_LOG_PATH = os.path.abspath(os.path.join(LOG_DIR, "fanar_raw.log"))

logger = logging.getLogger("fanar")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s [fanar]: %(message)s"))
    logger.addHandler(ch)
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
تُعطى لك بيانات المهمة الكتابية ومقال الطالب. قيّم المقال وفق معايير التقييم المرفقة فقط.
أعطِ لكل معيار درجة من 1 إلى 5:
1: غير متوافر إطلاقًا
2: ضعيف
3: متوسط
4: جيد
5: متوافر بشكل كامل

لكل معيار اكتب تعليقًا قصيرًا (15 كلمة كحد أقصى) يوضح سبب الدرجة بشكل عام.
إذا لم يحصل المعيار على الدرجة الكاملة (5)، أضف:
- في حقل "example": مثالًا حقيقيًا مأخوذًا حرفيًا من نص الطالب نفسه (جملة قصيرة أو عبارة دقيقة) يوضح أين لم يتحقق المعيار كاملاً.
- في حقل "detail": شرحًا موسّعًا (من جملتين إلى ثلاث جمل) يوضح بدقة: ما الذي كتبه الطالب في هذا الموضع تحديدًا، ولماذا يُعدّ ذلك نقصًا (مثلاً: لم يذكر أي مثال داعم، أو اكتفى بجملة واحدة دون تفصيل، أو لم يربط بين الفكرتين، أو الحجة ذُكرت دون دليل)، مع اقتراح محدد وقابل للتطبيق لكيفية تحسين هذا الموضع تحديدًا.
إذا حصل المعيار على الدرجة الكاملة اترك الحقلين "example" و"detail" فارغين.
تجاهل تمامًا علامات التشكيل (فتحة، ضمة، كسرة، سكون) في كل تقييمك؛ فهي ليست جزءًا من معايير التقييم إطلاقًا ولا تذكرها في أي تعليق. ركّز اهتمامك على اختيار الألفاظ ودقتها في السياق، وبنية الجمل والفقرات، وترابط الأفكار، وقوة الحجج والأمثلة، لا على التفاصيل الإملائية الدقيقة كالتشكيل.
بلا علامات اقتباس " داخل النص.
أعد الإجابة بصيغة JSON صِرف فقط، دون أي مقدمة أو شرح أو علامات ```json. ابدأ بـ { وانتهِ بـ }."""

SYSTEM_PROMPT_WRITING = """أنت معلّم لغة عربية خبير في تصحيح الأخطاء الإملائية والنحوية وإثراء المفردات لطلاب المرحلة الإعدادية.
تُعطى لك مقال الطالب. نفّذ ثلاث مهام:

## 1) الأخطاء اللغوية
استخرج بحد أقصى 5 أخطاء فعلية (الأبرز فقط)، من نوعين فقط: "إملائي" أو "نحوي".
قواعد صارمة:
- لا تُدرج أي ملاحظة متعلقة بعلامات التشكيل مثل الفتحة أو الضمة أو الكسرة أو السكون؛ فهذه ليست أخطاء مقصودة هنا إطلاقًا، ولا تذكرها ولو مرة واحدة.
- في الأخطاء النحوية، ركّز على القواعد الأساسية مثل: إنّ وأخواتها، كان وأخواتها، الفاعل والمفعول به،
  الأفعال الخمسة، جزم ونصب الفعل المضارع، والمطابقة بين المبتدأ والخبر.
- في الأخطاء الإملائية، ركّز على الهمزات، التاء المربوطة والمفتوحة، الألف اللينة، وحروف الجر الملتصقة.
- لكل خطأ حدد: النص الأصلي كما ورد بالضبط (original)، والتصحيح الصحيح (correction)،
  وشرحًا مبسطًا لسبب الخطأ في 15 كلمة كحد أقصى (explanation).

## 2) إثراء المفردات
اقرأ المقال وابحث عن كلمات أو تعبيرات ضعيفة أو مكرورة أو عامة جدًا (مثل: جيد جدًا، شيء، كبير، جميل، مهم جدًا)
أو مفردة استُخدمت أكثر من مرة دون تنويع. اختر بحد أقصى 5 كلمات من هذا النوع، ولكل كلمة أعطِ:
- الكلمة كما وردت في النص (word)
- الجملة أو العبارة القصيرة التي وردت فيها كما وردت بالضبط (context)
- قائمة من 2 إلى 3 بدائل عربية أقوى وأدق وأنسب للسياق نفسه (alternatives)
ركّز على قوة اختيار الألفاظ ودقتها في سياقها، لا على الشكل أو التشكيل.

## 3) الفقرة المحسّنة والتعليق العام
اكتب فقرة واحدة محسّنة مأخوذة من فقرة فعلية من المقال، وتعليقًا عامًا مشجعًا (15 كلمة كحد أقصى).

بلا علامات اقتباس " داخل قيم النصوص.
أعد الإجابة بصيغة JSON صِرف فقط، دون أي مقدمة أو شرح أو علامات ```json. ابدأ بـ { وانتهِ بـ }."""

def build_scores_messages(task: dict, essay: str) -> List[dict]:
    criteria_lines = "\n".join(f"- {c['name']} (الوزن: {c['weight']})" for c in task["rubric"])
    schema_scores = ",\n".join(f'    "{c["name"]}": 3' for c in task["rubric"])
    schema_feedback = ",\n".join(
        f'    "{c["name"]}": {{"comment": "تعليق قصير", "example": "مثال من نص الطالب أو فارغ", "detail": "شرح موسّع وسبب محدد واقتراح للتحسين أو فارغ"}}'
        for c in task["rubric"]
    )

    user_prompt = f"""## بيانات المهمة
النص:
{task['text']}

التخطيط للكتابة:
{task['planning']}

الإرشادات:
{task['guidelines']}

معايير التقييم (الوزن يدل على أهمية المعيار، لكنه لا يغيّر طريقة تقييمك للمعيار نفسه):
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
  "vocabulary_suggestions": [
    {{"word": "...", "context": "...", "alternatives": ["...", "..."]}}
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

def _clamp_score(value: Any) -> int:
    if not isinstance(value, (int, float)):
        return 0
    return max(0, min(5, int(round(value))))

def normalize_result(data: dict, task: dict) -> dict:
    data.setdefault("scores", {})
    data.setdefault("feedback", {})
    data.setdefault("mistakes", [])
    data.setdefault("vocabulary_suggestions", [])
    data.setdefault("improved_paragraph", "")
    data.setdefault("overall_comment", "")

    for criterion in task["rubric"]:
        name = criterion["name"]
        if name not in data["scores"] or not isinstance(data["scores"][name], (int, float)):
            data["scores"][name] = 0
            logger.warning(f"Missing/invalid score for criterion '{name}', defaulted to 0.")
        else:
            data["scores"][name] = _clamp_score(data["scores"][name])

        fb = data["feedback"].get(name)
        if isinstance(fb, dict):
            data["feedback"][name] = {
                "comment": fb.get("comment", "لم يتوفر تعليق لهذا المعيار."),
                "example": fb.get("example", ""),
                "detail": fb.get("detail", ""),
            }
        elif isinstance(fb, str):
            data["feedback"][name] = {"comment": fb, "example": "", "detail": ""}
        else:
            data["feedback"][name] = {
                "comment": "لم يتوفر تعليق لهذا المعيار في رد النموذج.",
                "example": "",
                "detail": "",
            }

    cleaned_mistakes = []
    for m in data["mistakes"]:
        if not isinstance(m, dict):
            continue
        mtype = m.get("type", "نحوي")
        if mtype not in ("إملائي", "نحوي"):
            mtype = "نحوي"
        cleaned_mistakes.append({
            "type": mtype,
            "original": m.get("original", ""),
            "correction": m.get("correction", ""),
            "explanation": m.get("explanation", ""),
        })
    data["mistakes"] = cleaned_mistakes

    cleaned_vocab = []
    for v in data.get("vocabulary_suggestions", []):
        if not isinstance(v, dict):
            continue
        alternatives = v.get("alternatives", [])
        if not isinstance(alternatives, list):
            alternatives = []
        alternatives = [str(a) for a in alternatives if str(a).strip()][:3]
        word = str(v.get("word", "")).strip()
        if not word or not alternatives:
            continue
        cleaned_vocab.append({
            "word": word,
            "context": str(v.get("context", "")).strip(),
            "alternatives": alternatives,
        })
    data["vocabulary_suggestions"] = cleaned_vocab[:5]

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
        "vocabulary_suggestions": [],
        "improved_paragraph": "",
        "overall_comment": "",
    }

    try:
        writing_messages = build_writing_messages(task, essay)
        writing_raw = client.chat(writing_messages)
        writing_data = extract_json(writing_raw)
        result["mistakes"] = writing_data.get("mistakes", [])
        result["vocabulary_suggestions"] = writing_data.get("vocabulary_suggestions", [])
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
        "rubric": [
            {"name": "إبداء الرأي الشخصي", "weight": 2},
            {"name": "قوة الحجج", "weight": 3},
        ],
    }
    sample_essay = "الألعاب الإلكترونية مفيدة لأنها تنمي التفكير والتركيز."
    print(evaluate_essay(sample_task, sample_essay))