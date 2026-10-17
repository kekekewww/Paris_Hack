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
