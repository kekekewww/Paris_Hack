"""Provider boundary. The configured default executes rules, not an LLM.

No external model client or credential is created here. A future model provider
must pass the same structural/source checks and be verified with real requests.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Protocol

from .retrieval import OfficialRetriever


class AIError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class ProviderUnavailableError(AIError):
    def __init__(self):
        super().__init__("LLM_NOT_CONFIGURED", "外部 LLM 尚未配置，沒有可驗證的真實模型連線。請使用明確標示的官方規則模式。", 503)


class ConversationProvider(Protocol):
    name: str

    async def respond(self, case: dict, message: str, document_id: str | None = None) -> dict: ...


CONDITION_OPTIONS = {"cause": {"unknown", "accident", "illness"}, "surgery": {"unknown", "yes", "no"},
                     "receipt_type": {"unknown", "actual", "daily"}, "payment_method": {"unknown", "remittance", "other"},
                     **{field: {"unknown", "yes", "no"} for field in ("first_claim", "diagnosis_has_surgery_details", "pathology_required_for_condition", "insurer_requested_medical_authorization", "insurer_requested_nhi_request")}}


def validate_assistant_response(payload: dict, retriever: OfficialRetriever) -> dict:
    """Reject unsupported states, fabricated source IDs/URLs, and invalid pages."""
    def invalid():
        raise AIError("INVALID_AI_RESPONSE", "回覆格式或官方引用未通過驗證，請重新確認。", 502)

    if not isinstance(payload, dict):
        invalid()
    required = {"response_type", "message", "suggested_claim_types", "missing_information", "source_references", "proposed_case_updates", "requires_human_review", "provider", "is_simulated"}
    if set(payload) != required or not isinstance(payload["response_type"], str) or payload["response_type"] not in {"answer", "uncertain", "clarification", "claim_suggestion"}:
        invalid()
    if not isinstance(payload["message"], str) or not payload["message"].strip() or len(payload["message"]) > 6000:
        invalid()
    if type(payload["requires_human_review"]) is not bool or type(payload["is_simulated"]) is not bool or not isinstance(payload["provider"], str):
        invalid()
    for field in ("suggested_claim_types", "missing_information", "source_references"):
        if not isinstance(payload[field], list):
            invalid()
    if any(not isinstance(item, str) for item in payload["missing_information"]):
        invalid()
    for suggested in payload["suggested_claim_types"]:
        if not isinstance(suggested, dict) or set(suggested) != {"id", "title", "description"} or not all(isinstance(v, str) for v in suggested.values()) or suggested["id"] not in retriever.claim_types:
            invalid()
    for source in payload["source_references"]:
        if not isinstance(source, dict):
            invalid()
        canonical = retriever.source(source.get("source_id", ""), source.get("page_number"))
        if canonical is None or source.get("official_url") != canonical["official_url"]:
            invalid()
    updates = payload["proposed_case_updates"]
    if not isinstance(updates, dict) or set(updates) - {"claim_type_id", "conditions"}:
        invalid()
    if updates and payload["response_type"] != "claim_suggestion":
        invalid()
    if "claim_type_id" in updates and (not isinstance(updates["claim_type_id"], str) or updates["claim_type_id"] not in retriever.claim_types):
        invalid()
    if "conditions" in updates:
        conditions = updates["conditions"]
        if not isinstance(conditions, dict) or any(key not in CONDITION_OPTIONS or not isinstance(value, str) or value not in CONDITION_OPTIONS[key] for key, value in conditions.items()):
            invalid()
    return deepcopy(payload)


UNCERTAINTY = re.compile(r"不確定|不知道|不清楚|有沒有|是否|可能|疑似|懷疑|尚未|還沒|未確診|沒有確診|待確認|打算|預計|將會|下[週周月次]|未來|如果|假設|計畫|(?:不能|無法)排除")
# Bind negation to the event itself. An unrelated symptom's negation earlier
# in the clause (e.g. 沒有咳嗽也有住院) must not negate the admission.
NEGATION = re.compile(r"(?:沒有|不是|未曾|不曾|未罹患|不用|不必|無需|不需|已排除|排除|無|沒|未|非)(?:曾經|需要|接受|進行|做過|做|發生|患有|罹患|辦理|有)?\s*$")
POST_NEGATION = re.compile(r"^\s*(?:已經|已|確定)?(?:沒有|未|沒)(?:做|進行|接受|施行|實施|辦理)|^\s*(?:已經|已)排除")


def _event_text(text: str) -> str:
    # Explicit current-visit markers prevent an older accident from becoming
    # the current case. Otherwise later descriptions can correct earlier ones.
    markers = list(re.finditer(r"這次|本次|此次", text))
    return text[markers[-1].end():] if markers else text


def _mention_state(text: str, pattern: str, *, surgery=False) -> bool | None:
    state = None
    for clause in re.split(r"[，,。；;！？?!\n]|但是|但|而是|只有", text):
        clause = re.sub(r"不是(?:沒|沒有)(住院|入院)", r"已\1", clause)
        for match in re.finditer(pattern, clause):
            before = clause[max(0, match.start() - 12):match.start()]
            after = clause[match.end():match.end() + 12]
            nearby = before + match.group() + after
            if UNCERTAINTY.search(nearby) or (surgery and re.search(r"會|需要|安排|預定|準備|尚未|還未", before)):
                state = None
            elif NEGATION.search(before) or POST_NEGATION.search(after):
                state = False
            elif re.search(r"不確定|不知道|不清楚|還沒|未確診|沒有確診", after):
                state = None
            else:
                state = True
    return state


def infer_description(messages: list[str]) -> dict:
    text = _event_text("，".join(messages))
    inpatient = _mention_state(text, r"住院|入院")
    outpatient = _mention_state(text, r"門診|看診")
    critical = _mention_state(text, r"癌症|罹癌|重大疾病")
    accident = _mention_state(text, r"車禍|意外|摔倒|跌倒")
    illness = _mention_state(text, r"疾病|生病|肺炎|感染|癌症|罹癌|腫瘤")
    surgery = _mention_state(text, r"手術|開刀", surgery=True)
    # A possible cancer mention cannot imply confirmed disease cause.
    cause = "accident" if accident is True and illness is not True else "illness" if illness is True and accident is not True else "unknown"
    return {"claim_type_id": "critical_illness" if critical is True else "inpatient" if inpatient is True else "outpatient" if outpatient is True else None,
            "conditions": {"cause": cause, "surgery": "yes" if surgery is True else "no" if surgery is False else "unknown", "receipt_type": "unknown"}}


def _base(message: str = "", response_type: str = "answer", references=None) -> dict:
    return {"response_type": response_type, "message": message, "suggested_claim_types": [], "missing_information": [],
            "source_references": references or [], "proposed_case_updates": {}, "requires_human_review": True,
            "provider": "grounded_rules", "is_simulated": False}


def _supported_preparation_question(message: str, has_document_context: bool) -> bool:
    """Conservative intent boundary for the small, verified local corpus.

    Keyword overlap alone is not sufficient support for new medical tests,
    legal interpretations, treatment, or deadlines absent from this index.
    """
    if re.search(r"[a-z]{2,}|英文|外文|電子簽|法律|效力|請求權|時效|期限|幾天|幾年|[一二三四五六七八九十]+年|治療|冰敷|用藥|吃藥|飲食|新冠|快篩", message, re.I):
        return False
    if has_document_context and re.search(r"這份|這個|怎麼準備|如何準備|怎麼填|如何填", message):
        return True
    if re.search(r"診斷書|診斷證明", message) and re.search(r"正本|副本|影本|影印|紅章|印章|格式|記載|載明|入院|出院|時間|病名|手術|內容", message):
        return True
    if re.search(r"手術", message) and re.search(r"文件|證明|紀錄|部位|方式|記載|另附", message):
        return True
    if re.search(r"收據", message) and re.search(r"正本|副本|影本|影印|門診|用途|準備|需要", message):
        return True
    if re.search(r"申請書|簽名|簽署", message) and re.search(r"填|欄位|本人|簽名|簽署|日期|格式|法定代理人", message):
        return True
    return bool(re.search(r"病理|檢驗報告|存摺|病歷.{0,5}授權|調閱.{0,5}範圍|健保.{0,6}(申請|資料)|調查同意|郵寄|寄到|送件地址|客服", message))


class GroundedRulesProvider:
    """Actual local rules and retrieval; deliberately makes no LLM claim."""
    name = "grounded_rules"

    def __init__(self, retriever: OfficialRetriever | None = None):
        self.retriever = retriever or OfficialRetriever()

    async def respond(self, case: dict, message: str, document_id: str | None = None) -> dict:
        retriever = self.retriever
        # These are safety-boundary references, never evidence of a claimed
        # amount, benefit, or medical diagnosis.
        scope_source = retriever.source("cardif-claims")
        scope_refs = [scope_source] if scope_source else []
        if re.search(r"忽略.{0,12}(指令|規則|系統)|忽略以上|system\s*:|輸出.{0,8}(金鑰|秘密)|所有文件.{0,8}(通過|核准)|改用\s*https?://", message, re.I):
            return _base("對話內容不能更改官方規則、文件檢查或案件狀態。我只能依已查核官方資料協助準備；無法確認的事項請洽官方客服。", "uncertain", scope_refs)
        if re.search(r"多少錢|給付金額|獲賠|賠多少|保證|核准|資格|一定.*賠|保障|[十百千萬億0-9]+元", message):
            return _base("目前無法確認個別保單的理賠資格、保障或給付金額，也不能核准或代送理賠。請查閱保單條款或洽官方客服 0800-012-899。以下官方來源說明的是程序及保單限制，並不支持任何個案給付結論。", "uncertain", scope_refs)
        if not case.get("claim_type_id"):
            if not scope_source:
                return _base("目前缺少可查核的官方分類來源，不能據此建立類別提案。請稍後重試或向官方確認。", "uncertain")
            prior = [item["content"] for item in case.get("messages", []) if item.get("role") == "user" and isinstance(item.get("content"), str)]
            proposal = infer_description(prior + [message])
            if not proposal["claim_type_id"]:
                answer = _base("請先確認本次是已住院、只有門診，或已由醫師確診癌症／重大疾病？不確定時可先核對就醫資料，我不會推定理賠資格。", "clarification", scope_refs)
                answer["missing_information"] = ["care_setting"]
                return answer
            claim = retriever.claim_types.get(proposal["claim_type_id"])
            if not claim:
                return _base("目前沒有可查核的分類資料，請向官方確認。", "uncertain")
            answer = _base(f"依您描述的本次就醫情形，可先檢視「{claim['label']}」的文件資訊。請確認類別與條件後再建立清單，是否符合給付仍依保單及官方審核。此回覆由本機規則產生，未使用外部 LLM。", "claim_suggestion", scope_refs)
            answer["suggested_claim_types"] = [{"id": claim["claim_type_id"], "title": claim["label"], "description": "請以本次就醫資料、個別保單與官方審核確認適用性。"}]
            answer["missing_information"] = [key for key, value in proposal["conditions"].items() if value == "unknown"]
            answer["proposed_case_updates"] = proposal
            return answer
        context = retriever.document_context(document_id, case["claim_type_id"]) if document_id else []
        if re.search(r"應備文件|準備.*哪些文件|哪些文件|文件清單", message):
            rules = [rule for rule in retriever.registry.get("rules", []) if rule["claim_type_id"] == case["claim_type_id"]]
            rules.sort(key=lambda rule: rule["requirement_type"] != "required")
            evidence = [chunk for rule in rules for chunk in retriever.document_context(rule["document_id"], case["claim_type_id"])]
            if evidence:
                lines = [f"{item['title']}：{item['text']}" for item in evidence]
                return _base("本類別的官方文件準備資訊：\n" + "\n".join(lines) + "\n條件式項目需先確認，請對照清單與保單；這不是給付或核准結論。", references=retriever.references(evidence))
        evidence = context + retriever.search(message, case["claim_type_id"], limit=2) if _supported_preparation_question(message, bool(context)) else []
        if not evidence:
            return _base("目前的官方資料沒有足夠依據回答這個問題。請向官方客服 0800-012-899 確認；我不會用不相關的程序來源充當此問題的依據。", "uncertain")
        excerpts = list(dict.fromkeys(f"{item['title']}：{item['text']}" for item in evidence))
        return _base("\n".join(excerpts[:3]) + "\n以上是已查核資料的準備說明；適用情形仍須依個別保單與承辦人確認，初步檢查不代表正式核准。", references=retriever.references(evidence))


class UnavailableLLMProvider:
    name = "unconfigured_llm"

    async def respond(self, case: dict, message: str, document_id: str | None = None) -> dict:
        raise ProviderUnavailableError()
