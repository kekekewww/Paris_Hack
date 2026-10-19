"""Deterministic, synthetic guided conversations; no model or network calls."""
import asyncio
import copy
import re

import httpx
import pytest

from backend.app.ai.openai_compatible import OpenAICompatibleProvider, OpenAICompatibleSettings
from backend.app.ai.providers import GroundedRulesProvider


def case(*history):
    return {"id": "synthetic-guided-followup", "claim_type_id": None,
            "conditions": {"cause": "unknown", "surgery": "unknown"}, "documents": [],
            "messages": [{"role": "user", "content": text} for text in history]}


def say(item, message):
    before = copy.deepcopy(item)
    answer = asyncio.run(GroundedRulesProvider().respond(item, message))
    assert item == before  # A proposal cannot establish a case or documents.
    item["messages"].extend([{"role": "user", "content": message},
                             {"role": "assistant", "content": answer["message"], "response": answer}])
    return answer


def assert_no_proposal(answer):
    assert answer["response_type"] == "clarification"
    assert answer["suggested_claim_types"] == []
    assert answer["proposed_case_updates"] == {}
    assert "care_setting" in answer["missing_information"]


def assert_does_not_reask_admission(answer):
    assert not re.search(r"是否.{0,5}住院|有沒有.{0,3}住院|已住院|確診癌症|重大疾病", answer["message"])


def test_greeting_accident_and_denied_admission_advance_to_the_remaining_question():
    item = case()
    greeting = say(item, "你好")
    assert_no_proposal(greeting)
    assert re.search(r"您好|你好|歡迎", greeting["message"])
    assert re.search(r"描述|發生", greeting["message"])

    accident = say(item, "我出車禍了")
    assert_no_proposal(accident)
    assert "車禍" in accident["message"]
    assert "住院" in accident["message"]

    no_admission = say(item, "沒有住院")
    assert_no_proposal(no_admission)
    assert_does_not_reask_admission(no_admission)
    assert all(word in no_admission["message"] for word in ("急診", "門診", "尚未就醫"))
    assert len({greeting["message"], accident["message"], no_admission["message"]}) == 3
    assert item["claim_type_id"] is None and item["documents"] == []


def test_known_denied_admission_is_preserved_across_a_general_followup():
    item = case("我出車禍了", "沒有住院")
    answer = say(item, "現在該怎麼辦？")
    assert_no_proposal(answer)
    assert_does_not_reask_admission(answer)
    assert "急診" in answer["message"] and "門診" in answer["message"]


def test_an_application_question_does_not_erase_an_explicit_denied_admission():
    answer = say(case("我出車禍了"), "沒有住院可以申請嗎？")
    assert_no_proposal(answer)
    assert_does_not_reask_admission(answer)
    assert "沒有住院" in answer["message"]
    assert "急診" in answer["message"] and "門診" in answer["message"]


def test_an_application_question_does_not_erase_a_completed_emergency_visit():
    answer = say(case("我出車禍了", "沒有住院"), "有去急診可以申請嗎？")
    assert answer["response_type"] == "claim_suggestion"
    assert answer["suggested_claim_types"][0]["id"] == "outpatient"
    assert "急診是否適用" in answer["message"]
    assert answer["requires_human_review"] is True


@pytest.mark.parametrize("message", ["有去急診，沒有手術", "昨天已經去急診了，沒有開刀", "有看門診，沒有手術"])
def test_confirmed_emergency_or_outpatient_visit_is_a_proposal_that_still_needs_confirmation(message):
    item = case("我出車禍了", "沒有住院")
    answer = say(item, message)
    assert answer["response_type"] == "claim_suggestion"
    assert [claim["id"] for claim in answer["suggested_claim_types"]] == ["outpatient"]
    assert answer["proposed_case_updates"]["conditions"]["cause"] == "accident"
    assert answer["proposed_case_updates"]["conditions"]["surgery"] == "no"
    assert "確認" in answer["message"] and "建立清單" in answer["message"]
    assert item["claim_type_id"] is None and item["documents"] == []


def test_emergency_suggestion_is_document_navigation_with_explicit_official_confirmation():
    answer = say(case("我出車禍了", "沒有住院"), "已去過急診")
    assert answer["suggested_claim_types"][0]["id"] == "outpatient"
    assert re.search(r"急診是否適用.{0,16}(保單|官方)", answer["message"])
    assert "確認" in answer["message"]
    assert answer["requires_human_review"] is True
    assert answer["source_references"]


@pytest.mark.parametrize("message,remaining", [
    ("沒有住院也沒有看門診", "急診"),
    ("沒有住院，也沒有看過門診", "急診"),
    ("沒有住院，門診沒有看", "急診"),
    ("沒有住院，也沒有去急診", "門診"),
    ("沒有住院，急診也沒有去", "門診"),
    ("沒有住院，沒有去過急診", "門診"),
    ("沒有住院，沒有到過急診", "門診"),
    ("沒有住院，沒有到急診", "門診"),
    ("沒有住院或門診", "急診"),
    ("沒有住院、門診或急診", "其他"),
])
def test_denied_care_settings_are_not_inferred_as_completed_visits(message, remaining):
    answer = say(case("我出車禍了"), message)
    assert_no_proposal(answer)
    assert_does_not_reask_admission(answer)
    assert remaining in answer["message"]
    assert "尚未就醫" in answer["message"]


@pytest.mark.parametrize("message", ["尚未就醫", "還沒有就醫", "我還沒看醫生"])
def test_no_medical_care_yet_is_acknowledged_without_repeating_the_generic_question(message):
    answer = say(case("我出車禍了"), message)
    assert_no_proposal(answer)
    assert re.search(r"尚未就醫|還未就醫|還沒有就醫", answer["message"])
    assert_does_not_reask_admission(answer)


@pytest.mark.parametrize("message", ["還不確定是否住院", "可能需要住院，但目前還不知道", "下週可能住院"])
def test_uncertain_or_future_admission_stays_unknown(message):
    answer = say(case("我出車禍了"), message)
    assert_no_proposal(answer)
    assert re.search(r"不確定|未知|核對", answer["message"])
    assert "已了解本次沒有住院" not in answer["message"]


@pytest.mark.parametrize("message", ["不一定有住院", "我沒有實際住院", "醫師說應該住院，但目前在家"])
def test_a_potential_or_negated_admission_is_not_a_completed_admission(message):
    assert_no_proposal(say(case("我出車禍了"), message))


@pytest.mark.parametrize("message", ["打算去急診", "明天要去急診", "準備去門診", "還沒看門診", "可能去看診",
                                     "急診需要住院嗎？", "還沒去急診", "沒有去急診也沒有門診", "急診"])
def test_future_or_uncertain_care_does_not_become_a_confirmed_outpatient_visit(message):
    answer = say(case("我出車禍了", "沒有住院"), message)
    assert_no_proposal(answer)


def test_current_visit_replaces_old_admission_and_surgery_history():
    item = case("去年因為肺炎住院並做過手術")
    answer = say(item, "本次是車禍，沒有住院")
    assert_no_proposal(answer)
    assert_does_not_reask_admission(answer)
    answer = say(item, "昨天已去急診")
    assert answer["suggested_claim_types"][0]["id"] == "outpatient"
    assert answer["proposed_case_updates"]["conditions"]["cause"] == "accident"
    assert answer["proposed_case_updates"]["conditions"]["surgery"] == "unknown"


def test_current_event_correction_changes_cause_without_changing_the_case():
    item = case("我出車禍了", "沒有住院")
    answer = say(item, "更正，本次不是車禍，是生病，只有門診")
    assert answer["suggested_claim_types"][0]["id"] == "outpatient"
    assert answer["proposed_case_updates"]["conditions"]["cause"] == "illness"
    assert item["conditions"]["cause"] == "unknown"


@pytest.mark.parametrize("message", ["更正，我沒有住院", "更正，本次還不確定是否住院", "更正，我尚未就醫"])
def test_later_correction_clears_an_earlier_admission_proposal(message):
    answer = say(case("我出車禍，住院三天"), message)
    assert_no_proposal(answer)


def test_assistant_history_is_not_treated_as_user_facts():
    item = case("我出車禍了")
    item["messages"].append({"role": "assistant", "content": "請問是住院還是已確診癌症？"})
    answer = say(item, "沒有住院")
    assert_no_proposal(answer)
    assert_does_not_reask_admission(answer)


@pytest.mark.parametrize("message", ["我一直咳嗽，擔心是癌症", "頭痛，會不會是癌症", "胸痛，很怕是重大疾病",
                                     "疑似感染，還沒有確診", "胸痛，是癌症嗎？", "咳嗽，我是不是有重大疾病"])
def test_symptoms_and_worries_do_not_establish_diagnosis_or_claim_type(message):
    answer = say(case(), message)
    assert_no_proposal(answer)


def test_confirmed_diagnosis_still_allows_a_source_grounded_proposal():
    answer = say(case(), "本次已由醫師確診癌症")
    assert answer["suggested_claim_types"][0]["id"] == "critical_illness"
    assert answer["source_references"]
    assert answer["requires_human_review"] is True


def test_later_confirmed_diagnosis_clears_an_earlier_no_care_statement():
    answer = say(case("尚未就醫"), "後來醫師已確診癌症")
    assert answer["response_type"] == "claim_suggestion"
    assert answer["suggested_claim_types"][0]["id"] == "critical_illness"
    assert answer["source_references"]
    assert answer["requires_human_review"] is True


@pytest.mark.parametrize("message", ["疑似癌症", "是癌症嗎？", "還不能確診癌症"])
def test_uncertain_diagnosis_does_not_override_an_earlier_no_care_statement(message):
    assert_no_proposal(say(case("尚未就醫"), message))


def test_guided_followups_do_not_send_history_or_facts_to_the_external_model():
    def unexpected_network(request):
        pytest.fail("Guided clarification and classification must not call the external model")

    provider = OpenAICompatibleProvider(OpenAICompatibleSettings(api_key="offline-synthetic-key", model="openrouter/free",
                                                               base_url="https://openrouter.ai/api/v1"),
                                        transport=httpx.MockTransport(unexpected_network))
    item = case("你好", "我出車禍了")
    answer = asyncio.run(provider.respond(item, "沒有住院"))
    assert_no_proposal(answer)
    assert answer["provider"] == "grounded_rules"
    assert_does_not_reask_admission(answer)
