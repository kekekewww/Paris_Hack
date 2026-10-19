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


UNCERTAINTY = re.compile(r"不確定|不知道|不清楚|有沒有|是否|是不是|會不會|可能|疑似|懷疑|擔心|擔憂|害怕|很怕|怕是|尚未|還沒|未確診|沒有確診|(?:不能|無法)確診|待確認|打算|預計|準備去|要去|將會|明天|後天|下[週周月次]|未來|如果|假設|計畫|(?:不能|無法)排除")
# Bind negation to the event itself. An unrelated symptom's negation earlier
# in the clause (e.g. 沒有咳嗽也有住院) must not negate the admission.
NEGATION = re.compile(r"(?:沒有|不是|未曾|不曾|未罹患|不需要|不用|不必|無需|不需|已排除|排除|無|沒|未|非)(?:實際)?(?:曾經|需要|接受|進行|做過|做|發生|患有|罹患|辦理|有|看過|看|去過|到過|到|去(?:看(?:過)?)?|掛)?\s*$")
POST_NEGATION = re.compile(r"^\s*(?:也)?(?:已經|已|確定)?(?:沒有|未|沒)(?:做|進行|接受|施行|實施|辦理|看過|看|去過|去|掛)|^\s*(?:已經|已)排除")
SHARED_CARE_NEGATION = re.compile(r"(?:沒有|沒|未曾|不曾)(?:實際)?\s*(?:(?:住院|入院|門診|急診)[、或及與和]\s*)+$")
NO_MEDICAL_CARE = re.compile(r"(?:尚未|還未|還沒(?:有)?|沒有|未曾|不曾|沒|未)(?:曾經|去)?(?:就醫|就診|看(?:過)?醫[生師])")


def _event_text(text: str) -> str:
    # Explicit current-visit markers prevent an older accident from becoming
    # the current case. Otherwise later descriptions can correct earlier ones.
    markers = list(re.finditer(r"這次|本次|此次", text))
    return text[markers[-1].end():] if markers else text


def _mention_state(text: str, pattern: str, *, surgery=False, care=False) -> bool | None:
    state = None
    for clause in re.split(r"[，,。；;！？?!\n]|但是|但|而是|只有", text):
        clause = re.sub(r"不是(?:沒|沒有)(住院|入院)", r"已\1", clause)
        for match in re.finditer(pattern, clause):
            before = clause[max(0, match.start() - 12):match.start()]
            after = clause[match.end():match.end() + 12]
            nearby = before + match.group() + after
            if UNCERTAINTY.search(nearby) or (surgery and re.search(r"會|需要|安排|預定|準備|尚未|還未", before)):
                state = None
            elif NEGATION.search(before) or POST_NEGATION.search(after) or (care and SHARED_CARE_NEGATION.search(before)):
                state = False
            elif care and re.search(r"不一定|應該|需要|準備|預定|安排|(?:將|會|要)\s*$", before):
                state = None  # A question or planned admission is not a completed visit.
            elif re.search(r"不確定|不知道|不清楚|還沒|未確診|沒有確診", after) or re.match(r"\s*(?:嗎|呢)", after):
                state = None
            else:
                state = True
    return state


def _description_state(messages: list[str]) -> dict:
    text = _event_text("，".join(messages))
    no_care = list(NO_MEDICAL_CARE.finditer(text))
    # A later correction such as 尚未就醫 clears earlier care assertions, while
    # retaining the event cause. Subsequent completed care can establish facts.
    care_text = text[no_care[-1].end():] if no_care else text
    inpatient = _mention_state(care_text, r"住院|入院", care=True)
    outpatient = _mention_state(care_text, r"門診|看診", care=True)
    emergency = _mention_state(care_text, r"急診", care=True)
    if emergency is True and not re.search(r"(?:去過|到過|有去|已去|已經去|去|到|只有)\s*急診|急診\s*(?:就醫|看診)", care_text):
        emergency = None
    critical = _mention_state(care_text, r"癌症|罹癌|重大疾病")
    confirmed_diagnosis = critical is True and bool(re.search(
        r"(?:(?:醫師|醫生).{0,4}|已(?:經)?(?:由醫師|由醫生)?)確診.{0,6}(?:癌症|罹癌|重大疾病)", care_text))
    not_yet_care = bool(no_care) and not confirmed_diagnosis and not any(value is True for value in (inpatient, outpatient, emergency))
    if not_yet_care:
        critical = None
    accident = _mention_state(text, r"車禍|意外|摔倒|跌倒")
    illness = _mention_state(text, r"疾病|生病|肺炎|感染|癌症|罹癌|腫瘤")
    surgery = _mention_state(care_text, r"手術|開刀", surgery=True)
    return {"text": text, "inpatient": inpatient, "outpatient": outpatient, "emergency": emergency,
            "critical": critical, "accident": accident, "illness": illness, "surgery": surgery,
            "admission_mentioned": bool(re.search(r"住院|入院", care_text)), "not_yet_care": not_yet_care}


def infer_description(messages: list[str]) -> dict:
    state = _description_state(messages)
    accident, illness, surgery = state["accident"], state["illness"], state["surgery"]
    # A possible cancer mention cannot imply confirmed disease cause.
    cause = "accident" if accident is True and illness is not True else "illness" if illness is True and accident is not True else "unknown"
    return {"claim_type_id": "critical_illness" if state["critical"] is True else "inpatient" if state["inpatient"] is True else "outpatient" if state["outpatient"] is True or state["emergency"] is True else None,
            "conditions": {"cause": cause, "surgery": "yes" if surgery is True else "no" if surgery is False else "unknown", "receipt_type": "unknown"}}


def _guided_clarification(state: dict, message: str) -> str:
    if state["not_yet_care"]:
        return "了解，您目前尚未就醫，我先不推定理賠類型。之後若有就醫，再依本次門診、急診或住院紀錄確認文件；是否適用仍須依保單及官方確認。"
    if state["inpatient"] is False:
        if state["outpatient"] is False and state["emergency"] is False:
            return "已了解本次沒有住院，也沒有門診或急診紀錄。是否有其他本次就醫資料，或目前尚未就醫？我先保留類型未知。"
        if state["outpatient"] is False:
            return "已了解本次沒有住院，也沒有看門診。請問是否曾到急診就醫，或目前尚未就醫？"
        if state["emergency"] is False:
            return "已了解本次沒有住院，也沒有去急診。請問是否曾看門診，或目前尚未就醫？"
        return "已了解本次沒有住院。請問是否曾到急診或門診就醫，還是目前尚未就醫？"
    if state["admission_mentioned"]:
        return "本次住院情形還不確定，我先保留未知。請核對本次就醫紀錄；目前能確認是否曾到門診或急診就醫嗎？"
    if state["accident"] is True:
        event = "車禍" if "車禍" in state["text"] else "意外"
        return f"了解，您提到本次發生{event}。請問目前是否已就醫，以及有沒有住院？我會依實際就醫情形協助確認文件。"
    if re.fullmatch(r"\s*(?:你好|您好|哈囉|嗨|hello|hi)[！!~～。，,.\s]*", message, re.I):
        return "您好，我可以協助整理理賠文件。請先簡單描述本次發生的情況，以及目前是否已就醫，我會再逐步確認。"
    return "請簡單描述本次發生的情況，以及已知的就醫紀錄，例如門診、急診或住院。不確定的部分可以先保留未知，我不會推定診斷或理賠資格。"


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
            descriptions = prior + [message]
            state = _description_state(descriptions)
            proposal = infer_description(descriptions)
            if not proposal["claim_type_id"]:
                answer = _base(_guided_clarification(state, message), "clarification", scope_refs)
                answer["missing_information"] = ["care_setting"]
                return answer
            claim = retriever.claim_types.get(proposal["claim_type_id"])
            if not claim:
                return _base("目前沒有可查核的分類資料，請向官方確認。", "uncertain")
            emergency_note = "急診是否適用仍待個別保單及官方確認。" if state["emergency"] is True and proposal["claim_type_id"] == "outpatient" else ""
            answer = _base(f"依您描述的本次就醫情形，可先檢視「{claim['label']}」的文件資訊。{emergency_note}請確認類別與條件後再建立清單，是否符合給付仍依保單及官方審核。此回覆由本機規則產生，未使用外部 LLM。", "claim_suggestion", scope_refs)
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
