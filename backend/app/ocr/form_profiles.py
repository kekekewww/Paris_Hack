"""Conservative label checks for the publicly verified VIE_Claim.2024.01.

Source: registry cardif-application, official CLAIM-1.1.1.pdf, pages 1-3,
rechecked 2026-10-26. These are label anchors, not a calibrated pixel template.
No inferred coordinates, legal signature checks, or blanket blank-cell rules.
"""
from dataclasses import dataclass


VERSION = "VIE_Claim.2024.01"


@dataclass(frozen=True)
class FieldRule:
    field: str
    name: str
    aliases: tuple[str, ...]


BASE_FIELDS = (
    FieldRule("insured_name", "被保人姓名", ("被保人姓名", "被保險人姓名", "Insured name")),
    FieldRule("policy_number", "保單號碼", ("保單號碼", "Policy number")),
    FieldRule("identity_number", "身分證字號", ("身分證字號", "身份證字號", "Identity number")),
    FieldRule("contact_phone", "連絡電話", ("連絡電話", "聯絡電話")),
    FieldRule("occupation", "事故當時職業／工作內容", ("事故當時職業/工作內容", "事故當時職業\\工作內容", "事故當時職業", "工作內容")),
    FieldRule("application_date", "簽署日期", ("簽署日期", "签署日期", "署日期", "申請日期", "Signed date")),
)
BANK_FIELDS = (
    FieldRule("account_holder", "戶名", ("戶名",)),
    FieldRule("bank_name", "銀行／郵局", ("銀行/郵局", "銀行／郵局")),
    FieldRule("bank_branch", "分行", ("分行",)),
    FieldRule("bank_account", "帳號", ("帳號", "帳戶號碼")),
)
ACCIDENT_FIELDS = (
    FieldRule("accident_datetime", "事故時間", ("事故時間",)),
    FieldRule("accident_location", "事故地點", ("事故地點",)),
    FieldRule("accident_description", "事故經過", ("事故經過", "經過說明")),
)
CHOICE_FIELDS = {
    "claim_selection": FieldRule("claim_selection", "申請項目", ("申請項目", "申请项目", "申請目", "Claim selection")),
    "claim_reason": FieldRule("claim_reason", "申請事由", ("申請事由",)),
    "other_insurer_claim": FieldRule("other_insurer_claim", "是否向其他公司申請理賠", ("本次事由是否向其他公司申請理賠", "其他公司申請理賠")),
    "payment_method": FieldRule("payment_method", "付款方式", ("付款方式",)),
    "tax_declaration": FieldRule("tax_declaration", "稅務聲明", ("稅務聲明", "本人僅為中華民國稅務居住者")),
}
TAX_QUESTIONS = (
    FieldRule("tax_taiwan_resident", "臺灣稅務居民身分", ("您是否具有臺灣稅務居民身分", "臺灣稅務居民身分")),
    FieldRule("tax_us_person", "美國納稅義務人身分", ("您是否具有美國納稅義務人身分", "美國納稅義務人身分")),
    FieldRule("tax_us_indicators", "美國身分指標", ("您具有下列任一項指標", "具有下列任一項指標")),
    FieldRule("tax_other_residency", "其他國家／地區稅務居民身分", ("您是否具有除臺灣及美國以外之其他國家或地區之稅務居民身分", "您是否具有除臺灣及美國以外之其他國家或地區之稅務居民身", "其他國家或地區之稅務居民身分", "其他國家或地區之稅務居民身")),
)
