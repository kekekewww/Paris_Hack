"""Deterministic Chinese lexical retrieval over the checked official registry.

The index is local. Queries and uploaded text never become URLs to fetch, and
only verified, allowlisted registry sources can accompany an evidence chunk.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit


REGISTRY_PATH = Path(__file__).resolve().parents[3] / "data" / "official-sources.json"
STOPWORDS = {"如何", "怎麼", "什麼", "可以", "是否", "需要", "還需", "要嗎", "嗎", "請問", "這份", "這個", "資料", "文件", "準備", "相關", "我的", "目前", "確認", "官方", "資訊", "申請", "保險", "理賠", "條件"}

# Reviewed paraphrases are deliberately local, not model prose. Each entry is
# usable only while the COMPLETE supporting paragraph, source and page match.
# A source revision therefore fails closed until its answer is reviewed again.
_ANSWER_CLAIMS = {
    "surgery-condition": ("surgery", "cardif-inpatient-guide", 3,
        "有手術、而診斷書缺少部位或方式時，另備手術證明；診斷書已記載，或未手術，指南說明可免另外提供。",
        "已手術且診斷書未載明手術部位或方式時，需另附手術證明。",
        "診斷書已記載手術部位與方式，或本次未手術，可依指南免另附；仍須向承辦人確認個案適用。"),
    "diagnosis-format": ("diagnosis_format", "cardif-inpatient-guide", 3,
        "診斷證明須用正本，或原醫療院所加蓋紅色印章的副本，普通影印本不符合指南要求。",
        "請準備診斷證明正本，或原醫療院所加蓋紅色印章的副本；普通影印本不符合指南要求。",
        "副本須由原醫療院所加蓋紅色印章，不能將一般影印本視為符合。"),
    "inpatient-diagnosis": ("diagnosis_contents", "cardif-general-documents", 1,
        "住院申請應檢查入出院時間、病名、手術及相關門診紀錄。手術申請另涉及費用明細或手術紀錄，適用情況須確認。",
        "住院診斷資料請檢查入院與出院時間、病名、手術及相關門診紀錄。",
        "涉及手術申請時，費用明細或手術紀錄的適用情況仍須確認。"),
    "outpatient-signature": ("outpatient_signature", "cardif-outpatient-guide", 1,
        "勾選門診，填寫被保險人資料並由本人簽署；未成年者須依年齡與法定代理人規定辦理。送件單位欄由銀行或保代填寫。",
        "門診申請請勾選門診、填寫被保險人資料並由本人簽署；送件單位欄由銀行或保代填寫。",
        "未成年者須依年齡與法定代理人規定辦理，不能一概套用成年本人簽署方式。"),
    "application-precheck": ("application_fields", "cardif-application", 1,
        "可初查姓名、保單號碼、身分證字號、聯絡方式、申請項目、付款方式、稅務聲明選項、申請人簽名與日期；不以辨識結果驗證法律真實性。",
        "申請書請檢查姓名、保單號碼、身分證字號、聯絡方式、申請項目、付款方式、稅務聲明選項、申請人簽名與日期。",
        "這是欄位初查；辨識結果不能驗證簽名或文件的法律真實性。"),
    "authorization-privacy": ("medical_authorization", "cardif-medical-authorization", 1,
        "授權書包含用途、查閱範圍與期限，應按實際需求及承辦人指示填寫，不由助手代勾授權範圍。",
        "病歷授權書的用途、查閱範圍與期限，請依實際需求及承辦人指示填寫。",
        "助手不代勾授權範圍；請先確認本案需要授權的內容。"),
    "critical-uncertainty": ("pathology", "cardif-critical-guide", 3,
        "指南列診斷與病理報告，並依手術及診斷書記載情形判斷是否另附手術證明；保單對疾病定義與給付條件仍待官方確認。",
        "重大疾病文件指南列有診斷與病理報告；手術證明依手術與診斷書記載情形判斷。",
        "疾病定義與給付條件仍待保單及官方確認，文件指南不能證明個案符合給付。"),
    "discrepancy:receipt-copy": ("receipt", "cardif-claims", None,
        "官網門診簡表寫收據正本，申請書第1頁載原收據有其他用途時可持副本申請。 保留原則與例外並提示向官方確認，不直接判定副本無效。",
        "門診收據原則列為正本；原收據有其他用途時，申請書另載副本申請的例外。",
        "須向官方確認個案能否適用副本例外，不能直接判定副本無效或一定可用。"),
    "submission": ("submission", "cardif-claims", None,
        "填妥申請書及適用文件郵寄至台北市信義區信義路五段7號79樓，法商法國巴黎人壽保險（股）台灣分公司 理賠部 收。客服0800-012-899，09:00–18:00（官網列上班時間）。",
        "備齊適用文件及填妥申請書後，可郵寄至台北市信義區信義路五段7號79樓，法商法國巴黎人壽保險（股）台灣分公司理賠部收。",
        "先確認投保險種與條款；官方客服為 0800-012-899，上班時間 09:00–18:00。助手不代送件。"),
}

_DOCUMENT_CLAIMS = {
    "application": ("使用官方四頁申請書；依個別情況填寫與簽署。", {"該理賠類別之官網清單包含保險金申請書。"},
        "請使用官方四頁保險金申請書，依個別情況填寫與簽署。", "填寫欄位與簽署方式仍依官方表單及個別情況確認。"),
    "diagnosis": ("向醫療院所申請；診斷書須為正本，或原醫療院所加蓋紅章之副本。", {"該理賠類別之官網清單包含診斷書或住院證明。"},
        "請向醫療院所申請診斷書或住院證明，診斷書須為正本或原院加蓋紅章的副本。", "一般影印本不等於原醫療院所加蓋紅章的副本。"),
    "receipt": ("向醫療院所取得。官網列正本；申請書另記原收據需作他用時可用副本，應向官方確認個案適用。", {"門診清單列收據正本；申請書有副本例外，須向官方確認。"},
        "門診收據請向醫療院所取得，原則列正本；原收據需作他用時另有副本例外。", "副本例外的個案適用須向官方確認。"),
    "surgery": ("由醫療院所提供；已手術且診斷書未記載手術部位、方式時另附。", {"有手術且診斷書未寫明手術部位、方式時另附；無手術或已記載者，依此指南不需另附。"},
        "已手術且診斷書未載明手術部位或方式時，需另附手術證明。", "診斷書已記載手術部位與方式，或本次未手術，可依指南免另附；仍須向承辦人確認個案適用。"),
    "passbook": ("選擇匯款給付時準備。", {"選擇匯款時需提供存摺影本。"},
        "選擇匯款給付時，需準備受款帳戶存摺影本。", "此項以選擇匯款給付為條件，未確認付款方式時不能直接認定必備。"),
    "medical_authorization": ("需要調閱病歷時依承辦人指示填寫；不能僅因指南有填寫教學即視為人人必備。", {"可能依病灶或審核需要要求，不預設為所有案件必備。"},
        "需要調閱病歷時，再依承辦人指示填寫病歷資料調閱授權書。", "不是所有案件都必備；是否需要及授權範圍須依個案確認。"),
    "accident_consent": ("官方標示供意外事故填寫；個案適用與填寫範圍向承辦人確認。", {"官方下載列表標示意外事故填寫，仍須確認個案是否須附與承辦人指定欄位。"},
        "調查同意書官方標示供意外事故填寫。", "本案是否須附及填寫範圍仍須向承辦人確認，不因提到意外就認定已必備。"),
    "nhi_request": ("官方依病灶可能要求；接獲通知後依承辦人指定範圍填寫。", {"收到官方通知時填寫；未通知時不能推定必須提供。"},
        "接獲官方通知後，再依承辦人指定範圍填寫健保資料申請書。", "未收到通知時不能推定必須提供。"),
    "pathology": ("由醫療院所提供；依病況、首次申請與保單約定確認。", {
        "官網標為依病況提供，不能由是否住院推定一律必備。",
        "一般文件注意事項明列首次癌症或重大疾病申請需病理或相關檢驗報告；非首次仍依病況、保單與承辦人確認。"},
        "病理組織或相關檢驗報告由醫療院所提供，須依病況、首次申請與保單約定確認。", "住院不能單獨推定一律必備；癌症或重大疾病首次申請與非首次的要求須分別確認。"),
}

_FACET_LABELS = {"surgery": "手術證明", "diagnosis_format": "診斷書格式", "diagnosis_contents": "診斷資料",
                 "application_fields": "申請書欄位", "outpatient_signature": "門診簽署", "receipt": "門診收據",
                 "medical_authorization": "病歷授權", "passbook": "存摺影本", "pathology": "病理報告",
                 "accident_consent": "意外調查同意書", "nhi_request": "健保資料申請書", "submission": "送件方式"}

# These are narrower questions than the verified paragraphs answer. Recognizing
# a document noun must never count as support for its every possible rule.
_UNSUPPORTED_SPECIFICS = (
    ("傳真或數位送件方式", r"傳真|電子送件|線上送件|電子郵件|手機照片|拍照送|掃描送"),
    ("期限或時效", r"多久|期限|時效|最晚|截止|有效期|何時以前|幾(?:個)?[天日週月年]|[0-9一二三四五六七八九十]+[天日週月年](?:內|後)"),
    ("填寫工具或筆色", r"藍筆|黑筆|紅筆|筆色|顏色|原子筆|鋼筆|鉛筆|用.{0,4}筆"),
    ("簽署或蓋章規則", r"(?:簽名|簽署|醫師|手術證明).{0,16}(?:蓋章|印章|簽章)|(?:蓋章|印章).{0,8}(?:代替|取代|簽名)|代簽"),
    ("欄位選項判斷", r"(?:稅務|付款方式|申請項目).{0,16}(?:勾哪|選哪|哪個|哪一|什麼|怎麼|如何|應勾|該勾)"),
    ("特定檢驗報告", r"\b(?:PCR|HIV)\b"),
)


def _answer_facets(query: str, document_id: str | None = None) -> list[str]:
    facets = []
    if re.search(r"手術|開刀", query) and re.search(r"證明|另附|部位|方式|紀錄|文件", query):
        facets.append("surgery")
    if re.search(r"診斷書|診斷證明", query) and re.search(r"正本|副本|影本|影印|紅章|印章|格式", query):
        facets.append("diagnosis_format")
    if re.search(r"診斷書|診斷證明", query) and re.search(r"入院|出院|病名|時間|內容|記載|載明", query) and "surgery" not in facets:
        facets.append("diagnosis_contents")
    if re.search(r"申請書|簽名|簽署|欄位|稅務聲明", query):
        facets.append("application_fields")
        if re.search(r"怎麼準備|如何準備", query) and not re.search(r"欄位|簽名|簽署|日期|填", query):
            facets[-1] = "application_document"
        if re.search(r"本人|未成年|代理人|送件單位|誰|誰來", query):
            facets[-1] = "outpatient_signature"
    for facet, pattern in (("receipt", r"收據"), ("medical_authorization", r"病歷.{0,5}授權|調閱.{0,5}範圍"),
                           ("passbook", r"存摺|匯款"), ("pathology", r"病理|檢驗報告"),
                           ("accident_consent", r"調查同意"), ("nhi_request", r"健保.{0,6}(?:申請|資料)"),
                           ("submission", r"郵寄|寄到|送件地址|客服")):
        if re.search(pattern, query):
            facets.append(facet)
    if not facets and document_id in _DOCUMENT_CLAIMS:
        facets.append({"application": "application_document", "diagnosis": "diagnosis_format"}.get(document_id, document_id))
    return list(dict.fromkeys(facets))


def allowed_source_url(value: object) -> bool:
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.hostname == "life.cardif.com.tw"
                and url.username is None and url.password is None
                and url.port in (None, 443) and not url.fragment
                and "\\" not in value and url.path.startswith("/"))
    except ValueError:
        return False


def tokens(value: str) -> set[str]:
    value = unicodedata.normalize("NFKC", value).lower()
    for before, after in (("診斷證明書", "診斷書"), ("診斷證明", "診斷書"), ("簽署", "簽名"), ("開刀", "手術"), ("重疾", "重大疾病")):
        value = value.replace(before, after)
    output = set()
    for run in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", value):
        if re.fullmatch(r"[a-z0-9_]+", run):
            output.add(run)
        else:
            output.update(run[index:index + 2] for index in range(len(run) - 1))
    return output - STOPWORDS


class OfficialRetriever:
    def __init__(self, registry: dict | None = None):
        self.registry = deepcopy(registry) if registry is not None else json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.sources = {entry["source_id"]: entry for entry in self.registry.get("sources", [])
                        if entry.get("verification_status") == "verified" and allowed_source_url(entry.get("official_url"))}
        self.claim_types = {item["claim_type_id"]: item for item in self.registry.get("claim_types", [])}
        self.chunks: list[dict] = []
        for item in self.registry.get("knowledge", []):
            self._add(item["knowledge_id"], item["title"], item["text"], item["source_id"], item.get("page_number"), weight=1.0)
        for rule in self.registry.get("rules", []):
            definition = next((item for item in self.registry.get("documents", []) if item["document_id"] == rule["document_id"]), None)
            if definition:
                self._add(f"document:{rule['claim_type_id']}:{rule['document_id']}", definition["title"],
                          f"{definition['description']} {rule['explanation']}", rule["source_id"], rule.get("page_number"),
                          [rule["claim_type_id"]], rule.get("additional_source_ids", []), weight=0.72,
                          document_id=rule["document_id"])
        for item in self.registry.get("discrepancies", []):
            source_ids = item.get("source_ids", [])
            if source_ids:
                self._add(f"discrepancy:{item['id']}", "來源差異與人工確認", f"{item['description']} {item['resolution']}",
                          source_ids[0], None, additional_ids=source_ids[1:], weight=0.9)
        submission = self.registry.get("submission", {})
        if submission:
            postal = submission.get("postal", {})
            support = submission.get("support", {})
            self._add("submission", "郵寄送件與官方客服", f"填妥申請書及適用文件郵寄至{postal.get('address', '')}，{postal.get('recipient', '')}。客服{support.get('phone', '')}，{support.get('hours', '')}。", submission.get("source_id", ""), None)
        frequencies = Counter(token for chunk in self.chunks for token in chunk["tokens"])
        self.idf = {token: 1 + math.log((len(self.chunks) + 1) / (count + 1)) for token, count in frequencies.items()}

    def source(self, source_id: str, page_number: int | None = None) -> dict | None:
        if not isinstance(source_id, str):
            return None
        source = self.sources.get(source_id)
        if not source:
            return None
        if page_number is not None and (type(page_number) is not int or page_number < 1 or page_number > (source.get("page_count") or 0)):
            return None
        return {**deepcopy(source), "page_number": page_number if page_number is not None else source.get("page_number")}

    def _add(self, knowledge_id, title, text, source_id, page_number, claim_types=None, additional_ids=None, weight=1.0, document_id=None):
        source = self.source(source_id, page_number)
        if not source:
            return
        references = [source]
        for additional in additional_ids or []:
            reference = self.source(additional)
            if reference:
                references.append(reference)
        self.chunks.append({"knowledge_id": knowledge_id, "title": title, "text": text,
                            "source": source, "source_references": references,
                            "claim_types": claim_types or source.get("related_claim_types", []),
                            "document_id": document_id, "tokens": tokens(title + " " + text), "weight": weight})

    def search(self, query: str, claim_type_id: str | None = None, limit: int = 3) -> list[dict]:
        query_tokens = tokens(query)
        if not query_tokens:
            return []
        ranked = []
        for chunk in self.chunks:
            if claim_type_id and claim_type_id not in chunk["claim_types"]:
                continue
            overlap = query_tokens & chunk["tokens"]
            if not overlap:
                continue
            score = sum(self.idf[token] for token in overlap) / math.sqrt(max(len(chunk["tokens"]), 1)) * chunk["weight"]
            ranked.append((score, chunk))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["knowledge_id"]))
        results, seen = [], set()
        for score, chunk in ranked:
            key = (chunk["source"]["source_id"], chunk["text"])
            if key not in seen:
                results.append({key: deepcopy(value) for key, value in chunk.items() if key not in ("tokens", "weight") } | {"score": round(score, 5)})
                seen.add(key)
            if len(results) >= max(1, min(limit, 5)):
                break
        return results

    def document_context(self, document_id: str, claim_type_id: str | None) -> list[dict]:
        return [{key: deepcopy(value) for key, value in item.items() if key not in ("tokens", "weight")} | {"score": 1.0}
                for item in self.chunks if item.get("document_id") == document_id and claim_type_id in item["claim_types"]]

    def _answer_claim(self, evidence: dict) -> tuple[str, str, str] | None:
        """Return one reviewed claim only after verifying its complete support."""
        claim = _ANSWER_CLAIMS.get(evidence.get("knowledge_id"))
        if claim:
            facet, source_id, page, text, direct, conditions = claim
            source = evidence.get("source", {})
            if (evidence.get("text") == text and source.get("source_id") == source_id
                    and source.get("page_number") == page and self.source(source_id, page)):
                if facet == "receipt" and not {"cardif-claims", "cardif-application"} <= {
                        item["source_id"] for item in self.references([evidence])}:
                    return None
                return facet, direct, conditions
            return None
        document_id = evidence.get("document_id")
        if document_id not in _DOCUMENT_CLAIMS:
            return None
        description, explanations, direct, conditions = _DOCUMENT_CLAIMS[document_id]
        source_id, page = ("cardif-claims", None)
        if document_id == "surgery":
            source_id, page = ("cardif-critical-guide" if "critical_illness" in evidence.get("claim_types", [])
                               else "cardif-inpatient-guide", 3)
        if document_id == "pathology" and "critical_illness" in evidence.get("claim_types", []):
            source_id, page = "cardif-general-documents", 1
        source = evidence.get("source", {})
        if (evidence.get("text") not in {f"{description} {explanation}" for explanation in explanations}
                or source.get("source_id") != source_id or source.get("page_number") != page
                or not self.source(source_id, page)):
            return None
        if document_id == "receipt" and "cardif-application" not in {
                item["source_id"] for item in self.references([evidence])}:
            return None
        if document_id == "pathology" and "critical_illness" in evidence.get("claim_types", []):
            direct = "首次癌症或重大疾病申請需附病理或相關檢驗報告。"
            conditions = "非首次申請仍依病況、保單與承辦人確認；不能因此推定每次要求皆相同。"
        # A document-name rule does not support detailed field/signature claims.
        facet = {"application": "application_document", "diagnosis": "diagnosis_format"}.get(document_id, document_id)
        return facet, direct, conditions

    def answer_context(self, query: str, claim_type_id: str | None, document_id: str | None = None) -> list[dict]:
        """Include precise supported facets so lexical overlap cannot crowd them out."""
        facets = _answer_facets(query, document_id)
        results = []
        for item in self.chunks:
            if claim_type_id and claim_type_id not in item["claim_types"]:
                continue
            claim = self._answer_claim(item)
            if claim and claim[0] in facets:
                results.append({key: deepcopy(value) for key, value in item.items() if key not in ("tokens", "weight")} | {"score": 1.0})
        return results

    def answer_gap(self, query: str) -> dict | None:
        query = unicodedata.normalize("NFKC", query)
        unsupported = [label for label, pattern in _UNSUPPORTED_SPECIFICS if re.search(pattern, query, re.I)]
        if unsupported:
            return {"response_type": "uncertain", "message": "關於" + "、".join(unsupported)
                    + "，目前已查核的官方證據不足以回答這些具體問題。請向官方確認；不以一般文件欄位或準備說明代替所缺的依據。",
                    "source_references": []}
        return None

    def is_preparation_question(self, query: str, document_id: str | None = None) -> bool:
        return bool(document_id or _answer_facets(query) or self.answer_gap(query)
                    or re.search(r"文件|表單|條款|填寫|怎麼填|如何填", query))

    def controlled_answer(self, query: str, selected: list[dict], document_id: str | None = None) -> dict:
        """Compose direct answers from verified local claims, never generated prose.

        IDs chosen by a model establish neither relevance nor entailment. Only
        claims matching a requested facet are used/cited; missing facets remain
        explicit. User statements select conditional wording, never case facts.
        """
        gap = self.answer_gap(query)
        if gap:
            return gap
        facets = _answer_facets(query, document_id)
        checklist = bool(re.search(r"應備文件|準備.*哪些文件|哪些文件|文件清單", query))
        supported = []
        for item in selected:
            claim = self._answer_claim(item)
            if (item.get("knowledge_id") == "critical-uncertainty" and re.search(r"首次|初次|第一次", query)):
                # The overview mentions pathology but contains no first-claim
                # rule. An official overview is insufficient for this facet.
                continue
            if claim and (checklist or claim[0] in facets):
                if claim[0] not in {current[1][0] for current in supported}:
                    supported.append((item, claim))
        if not supported:
            return {"response_type": "uncertain", "message": "本次已選官方證據不足以直接回答這個問題。請補充問題或向官方客服確認；我不會用相關但未支持問題的段落充當答案。",
                    "source_references": []}
        used = [item for item, _ in supported]
        references = self.references(used)
        direct_lines, condition_lines = [], []
        for item, (facet, direct, conditions) in supported:
            if facet == "surgery":
                # Keep both branches conditional. Do not treat the user's query
                # as validated facts or infer complete details from one keyword.
                no_surgery = bool(re.search(
                    r"(?:本次)?(?:沒有|未|無|沒)(?:做|接受|進行)?手術(?=$|[，,。；;、!?？！\s]|但|也|仍|還|所以|請|想|的話|是否)", query))
                recorded = bool(re.search(r"(?:已|已經)(?:完整)?(?:記載|載明).{0,10}部位.{0,5}方式", query))
                ambiguous = bool(re.search(r"不是|並未|未記載|未載明|沒有記載|不完整|只有|還沒|尚未|將|預計|可能|不確定", query))
                if no_surgery and not re.search(r"不是|並非|不確定|不知道|不清楚|可能", query):
                    direct = "若本次未手術，可免另附手術證明。"
                elif recorded and not ambiguous:
                    direct = "若診斷書已記載手術部位與方式，可免另附手術證明。"
            if facet == "diagnosis_format" and re.search(r"普通|一般|影印", query):
                direct = "普通影印本不符合指南要求；請準備正本或原醫療院所加蓋紅色印章的副本。"
            if facet == "application_fields" and not re.search(r"哪些|所有|欄位", query):
                fields = [label for pattern, label in ((r"姓名", "姓名"), (r"保單號碼", "保單號碼"),
                          (r"身分證", "身分證字號"), (r"聯絡", "聯絡方式"), (r"申請項目", "申請項目"),
                          (r"付款", "付款方式"), (r"稅務", "稅務聲明選項"), (r"簽名|簽署", "申請人簽名"),
                          (r"日期", "日期")) if re.search(pattern, query)]
                if fields:
                    direct = "請檢查申請書的" + "與".join(fields) + "是否填妥。"
            if (facet == "pathology" and item.get("document_id") == "pathology"
                    and "critical_illness" in item.get("claim_types", [])
                    and re.search(r"非首次|不是首次|不是第一次|非初次|再次|第二次", query)):
                direct = "非首次申請的病理或相關檢驗報告，仍依病況、保單與承辦人確認。"
                conditions = "首次癌症或重大疾病申請需附病理或相關檢驗報告；不能將首次要求直接套用到每次申請。"
            item_refs = self.references([item])
            markers = "".join(f"[{references.index(source) + 1}]" for source in item_refs)
            direct_lines.append(f"{direct} {markers}")
            condition_lines.append(f"{conditions} {markers}")
        lines = ["直接回答：" + "；".join(direct_lines), "適用條件：" + "；".join(condition_lines)]
        covered = {claim[0] for _, claim in supported}
        for facet in facets:
            if facet not in covered:
                lines.append(f"{_FACET_LABELS.get(facet, '此子題')}：本次證據不足，尚無法回答，請向官方確認。")
        if checklist:
            lines.append("本次只整理以上已選項目，完整應備清單與條件請查看工作區；未列項目不代表免附。")
        for index, source in enumerate(references, 1):
            page = f"第 {source['page_number']} 頁" if source.get("page_number") else "官方頁面"
            lines.append(f"來源 [{index}]：{source['title']}（{page}）")
        lines.append("適用情形仍依個別保單及官方確認；初步檢查不代表正式核准。")
        return {"response_type": "answer", "message": "\n".join(lines), "source_references": references}

    def references(self, evidence: list[dict]) -> list[dict]:
        references = []
        seen = set()
        for item in evidence:
            for source in item.get("source_references", []):
                canonical = self.source(source.get("source_id", ""), source.get("page_number"))
                if canonical:
                    key = (canonical["source_id"], canonical["page_number"])
                    if key not in seen:
                        references.append(canonical)
                        seen.add(key)
        return references
