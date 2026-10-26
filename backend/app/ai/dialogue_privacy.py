"""外送對話的資料最小化與明顯個資遮罩；不代表全面去識別化。

只處理呼叫者傳入的文字與歷史，不讀檔、不存取案件或文件、不記錄內容。
截斷前先遮罩；優先保留本次完整訊息與較新的引導資訊。
"""
from __future__ import annotations

import re


_MASK = "［遮罩］"
_WIDTH_TRANSLATION = {code: code - 0xFEE0 for start, end in ((0xFF10, 0xFF19), (0xFF21, 0xFF3A), (0xFF41, 0xFF5A))
                      for code in range(start, end + 1)}
_WIDTH_TRANSLATION.update(str.maketrans("＠．＿－＋＝（）", "@._-+=()"))
_CJK = r"\u3400-\u4dbf\u4e00-\u9fff"
_NUMBER = r"0-9一二三四五六七八九十百零〇"
_QUALIFIER = (r"不確定|不知道|不清楚|有沒有|是否|是不是|會不會|可能|疑似|懷疑|擔心|擔憂|害怕|很怕|怕是|"
              r"未確診|沒有確診|待確認|打算|預計|準備去|要去|將會|明天|後天|下[週周月次]|未來|如果|假設|計畫|"
              r"不能排除|無法排除|不是|不曾|未曾|已排除|排除|不需要|不用|不必|不需|無需")
_FACT = rf"(?:{_QUALIFIER}|沒有|尚未|還沒|(?:未|沒|無|不)(?:住院|入院|手術|開刀|就醫|看診|癌症|罹癌|重大疾病)|已經|住院|急診|門診|車禍|意外|手術|開刀|確診|昨天|今天|本次|這次)"
_END = rf"(?=[，,。；;！？!?\n\s]|{_FACT}|$)"

_SECRET = re.compile(
    r"(?:\bapi[ _-]*key\b|\b(?:access[ _-]*|auth[ _-]*)?token\b|\bsecret\b|\bauthorization\b|"
    r"API金鑰|金鑰|密鑰|秘鑰|權杖|憑證|密碼)(?:是|為)?[ \t:：=]+(?:Bearer[ \t]+)?"
    r'''(?:"[^"\r\n]+"|'[^'\r\n]+'|[^\s，,。；;！？!?]+)''', re.I)
_RAW_KEY = re.compile(r"(?<![A-Za-z0-9])sk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])", re.I)
_IDENTITY = re.compile(r"(?<![A-Za-z0-9])[A-Z][1289][0-9]{8}(?![A-Za-z0-9])", re.I)
_EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.I)
_PHONE = re.compile(
    r"(?<![0-9])(?:"
    r"(?:\+?886[ \t-]?(?:\(0\)|0)?[ \t-]?|0)9[0-9]{2}[ \t-]?[0-9]{3}[ \t-]?[0-9]{3}"
    r"|(?:\(0[2-8][0-9]?\)|0[2-8][0-9]?)[ \t-]?[0-9]{3,4}[ \t-]?[0-9]{3,4}"
    r"|\+?886[ \t-]?[2-8][0-9]?[ \t-]?[0-9]{3,4}[ \t-]?[0-9]{3,4}"
    r"|080[09][ \t-]?[0-9]{3}[ \t-]?[0-9]{3})(?![0-9])")
_ACCOUNT = re.compile(
    r"(?:銀行帳號|帳[戶號]|保單(?:號碼|編號|號)|身分[證証](?:字號|號碼)?)(?:是|為)?[ \t:：=]*"
    r"[A-Za-z0-9][A-Za-z0-9 \t-]{3,40}")
_LONG_NUMBER = re.compile(r"(?<![0-9])[0-9](?:[ \t-]?[0-9]){9,}(?![0-9])")
_NAME = re.compile(
    r"(?:我的姓名|本人姓名|我叫|姓名|名字|\bname\b)(?:是|為|叫)?[ \t:：=]*"
    rf"(?:[{_CJK}]{{2,4}}?{_END}|[{_CJK}]{{2,4}}|"
    r"[A-Za-z][A-Za-z'-]*(?:[ \t]+[A-Za-z][A-Za-z'-]*){0,2})", re.I)
_CITY = (r"(?:[臺台]北市|新北市|桃園市|[臺台]中市|[臺台]南市|高雄市|基隆市|新竹[縣市]|"
         r"苗栗縣|彰化縣|南投縣|雲林縣|嘉義[縣市]|屏東縣|宜蘭縣|花蓮縣|[臺台]東縣|澎湖縣|金門縣|連江縣)")
_ADDRESS = re.compile(
    rf"{_CITY}[{_CJK}0-9A-Za-z \t之-]{{1,70}}?"
    rf"[{_NUMBER}]+號(?:之[{_NUMBER}]+)?(?:[ \t]*[{_NUMBER}]+樓(?:之[{_NUMBER}]+)?)?")
_STREET = re.compile(rf"{_CITY}[{_CJK}0-9A-Za-z \t之-]{{1,50}}?(?:路|街|大道)(?:[{_NUMBER}]+段)?")
_LABELLED_ADDRESS = re.compile(
    r"(?:通訊地址|聯絡地址|住址|地址|住所)(?:是|為)?[ \t:：=]*"
    rf"[^\n，。；;！？!?]{{3,}}?(?=[\n，。；;！？!?]|{_FACT}|$)")
_SHORT_ANSWER = re.compile(r"\s*(?:有|沒有|是|不是)[，,。.!！?？~～\s]*\Z")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。；;！？!?\n])|(?<=[，,])(?=更正|請問|本次|這次|目前)")


def redact_text(text: str) -> str:
    """遮罩常見明顯識別資料；自由敘述仍可能包含未辨識的個資。"""
    if not isinstance(text, str):
        raise TypeError("對話內容必須是純文字。")
    text = text.translate(_WIDTH_TRANSLATION)
    for pattern in (_SECRET, _RAW_KEY, _IDENTITY, _EMAIL, _PHONE, _ACCOUNT,
                    _LONG_NUMBER, _NAME, _LABELLED_ADDRESS, _ADDRESS, _STREET):
        text = pattern.sub(_MASK, text)
    return text


def _document_scope(message: dict) -> bool:
    response = message.get("response")
    return (message.get("document_id") is not None
            or isinstance(response, dict) and response.get("document_id") is not None)


def _paired_assistant(history: list, user_index: int) -> tuple[int, dict] | None:
    # Another user starts a new turn; do not pair that user's answer backwards.
    for index in range(user_index + 1, len(history)):
        item = history[index]
        if not isinstance(item, dict):
            continue
        if item.get("role") == "user":
            return None
        if item.get("role") == "assistant":
            return index, item
    return None


def _history_suffix(text: str, limit: int) -> str:
    """只在完整句段邊界縮減歷史，避免將「沒有」截成「有」。"""
    text = redact_text(text)
    if len(text) <= limit:
        return text
    selected, length = [], 0
    for sentence in reversed(_SENTENCE_BOUNDARY.split(text)):
        if length + len(sentence) > limit:
            break
        selected.append(sentence)
        length += len(sentence)
    return "".join(reversed(selected))


def prepare_dialogue(history: list, current: str) -> list[dict[str, str]]:
    """最多八則歷史加本次訊息；內容合計最多 6000 字。

    本次純文字須為 1–4000 字，保留完整遮罩結果。歷史 user 上限 1000、
    assistant 上限 600 字；只保留完整句段。除最後一則引導回覆外，只保留
    「有／沒有／是／不是」短答所必要的前一個已確認 clarification 問句。
    無配對回覆的舊 user 歷史可保留，無法確認類型的配對輪次則不外送。
    """
    if not isinstance(current, str):
        raise TypeError("目前訊息必須是純文字。")
    if not current.strip() or len(current) > 4000:
        raise ValueError("目前訊息必須介於 1 至 4000 字。")
    current = redact_text(current)
    if len(current) > 4000:
        raise ValueError("遮罩後的目前訊息超過長度限制。")
    history = history if isinstance(history, list) else []
    assistant_indices = [index for index, item in enumerate(history)
                         if isinstance(item, dict) and item.get("role") == "assistant"]
    last_assistant = assistant_indices[-1] if assistant_indices else None
    candidates, safe_assistants, dependencies = [], {}, {}
    for index, item in enumerate(history):
        if (not isinstance(item, dict) or item.get("role") != "user" or _document_scope(item)
                or not isinstance(item.get("content"), str) or not item["content"].strip()):
            continue
        paired = _paired_assistant(history, index)
        if paired is not None:
            assistant_index, reply = paired
            response = reply.get("response")
            if (_document_scope(reply) or not isinstance(response, dict)
                    or not isinstance(response.get("response_type"), str)
                    or response.get("response_type") not in {"clarification", "claim_suggestion", "case_update_proposal"}):
                continue
        candidates.append((index, "user", item["content"]))
        if paired is not None:
            safe_assistants[assistant_index] = reply
    for index, _, content in candidates:
        previous = safe_assistants.get(index - 1)
        if (_SHORT_ANSWER.fullmatch(content) and previous is not None
                and previous["response"]["response_type"] == "clarification"):
            dependencies[index] = index - 1
    necessary = set(dependencies.values())
    if last_assistant in safe_assistants:
        necessary.add(last_assistant)
    for index in necessary:
        content = safe_assistants[index].get("content")
        if isinstance(content, str) and content.strip():
            candidates.append((index, "assistant", content))
    candidates.sort(key=lambda item: item[0])
    remaining = 6000 - len(current)
    selected = []
    for index, role, content in reversed(candidates[-8:]):
        limit = min(1000 if role == "user" else 600, remaining)
        if limit <= 0:
            break
        # Redact before clipping to avoid exposing fragments of an identifier.
        content = _history_suffix(content, limit)
        if content.strip():
            selected.append((index, {"role": role, "content": content}))
            remaining -= len(content)
    retained_questions = {index for index, message in selected
                          if message["role"] == "assistant"
                          and message["content"] == redact_text(safe_assistants[index]["content"])}
    return [message for index, message in reversed(selected)
            if index not in dependencies or dependencies[index] in retained_questions] + [{"role": "user", "content": current}]
