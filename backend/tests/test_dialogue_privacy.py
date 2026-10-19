"""Synthetic privacy boundaries; no credentials, model requests, or file inputs."""
import copy
import importlib

import pytest


def privacy():
    try:
        return importlib.import_module("backend.app.ai.dialogue_privacy")
    except ModuleNotFoundError as error:
        pytest.fail(f"Dialogue privacy boundary is not implemented: {error}")


def user(content, **extra):
    return {"role": "user", "content": content, **extra}


def assistant(content, response_type="clarification", **extra):
    return {"role": "assistant", "content": content,
            "response": {"response_type": response_type}, **extra}


@pytest.mark.parametrize("sensitive", [
    "A123456789", "a123456789", "B223456789", "0912345678", "0912-345-678",
    "+886 912 345 678", "(02)2345-6789", "037-123-456", "0800-012-899",
    "claim+demo@example.com", "12345678901234", "123-456-789-012",
    "保單號碼：POL-12345678", "帳號：1234567890", "姓名：陳美玲", "我叫王小明",
    "姓名: Kevin Yang", "臺北市信義區松仁路123號5樓", "台中市西區公益路100號",
    "地址：新竹市東區合成路15號", "住址：Synthetic Road 123, Demo City",
    'API Key: "sk-demo-1234567890"', "api_key=demo_private_key_123",
    "token=demo_token_123456", "金鑰：demo_secret_123456", "密碼：demo_password_123",
    "Authorization: Bearer demo_access_token_123",
])
def test_obvious_identifiers_are_removed_without_losing_the_care_facts(sensitive):
    result = privacy().redact_text(sensitive + "；車禍，沒有住院，尚未手術")
    assert sensitive not in result
    assert "車禍，沒有住院，尚未手術" in result
    assert result != sensitive + "；車禍，沒有住院，尚未手術"


def test_common_labelled_values_are_removed_completely_and_stop_at_newlines():
    text = '姓名：王小明\nAPI Key: "sk-demo-1234567890"\n沒有住院，只有門診'
    result = privacy().redact_text(text)
    for fragment in ("王小明", "sk-demo-1234567890", "demo-1234567890"):
        assert fragment not in result
    assert "沒有住院，只有門診" in result


def test_redaction_preserves_dates_small_clinical_numbers_and_negation():
    text = "2026-10-20車禍，住院3天，門診2次，沒有手術，可能肺炎但尚未確診"
    assert privacy().redact_text(text) == text


def test_names_and_unlabelled_addresses_do_not_consume_following_care_facts():
    text = "我叫王小明住院三天；臺北市信義區松仁路123號5樓，沒有手術"
    result = privacy().redact_text(text)
    assert "王小明" not in result and "松仁路" not in result
    assert "住院三天" in result and "沒有手術" in result


@pytest.mark.parametrize("fact", ["未住院", "沒住院", "無住院", "未手術", "沒開刀",
                                  "不確定是否住院", "可能住院", "未確診癌症", "不是癌症", "不需要住院"])
def test_name_redaction_does_not_remove_a_following_medical_negation(fact):
    result = privacy().redact_text("我叫王小明" + fact)
    assert "王小明" not in result
    assert fact in result


@pytest.mark.parametrize("sensitive,fragments", [
    ("Ａ１２３４５６７８９", ("Ａ１２３", "A123")),
    ("臺北市信義區松仁路１２３號５樓", ("松仁路", "１２３", "123")),
    ("claim＠example．com", ("claim", "example")),
])
def test_obvious_fullwidth_identifiers_are_redacted(sensitive, fragments):
    result = privacy().redact_text(sensitive + "，沒有住院")
    assert not any(fragment in result for fragment in fragments)
    assert "沒有住院" in result


def test_long_labelled_credentials_and_addresses_leave_no_unmasked_tail():
    text = "token=" + "a" * 600 + "SECRET-TAIL；地址：" + "合" * 130 + "ADDRESS-TAIL；沒有住院"
    result = privacy().redact_text(text)
    assert "SECRET-TAIL" not in result and "ADDRESS-TAIL" not in result
    assert "沒有住院" in result


def test_redaction_is_stable_when_called_again():
    once = privacy().redact_text("我叫陳大明，電話0912-345-678，沒有住院")
    assert privacy().redact_text(once) == once


def test_current_message_is_retained_and_only_role_and_redacted_plain_content_are_sent():
    history = [user("我叫王小明，我出車禍了", id="private-case-id", upload={"raw": "UPLOAD-CANARY"}),
               assistant("請問有沒有住院？", response_type="clarification", id="private-message-id")]
    before = copy.deepcopy(history)
    result = privacy().prepare_dialogue(history, "沒有住院，電話0912345678")
    assert history == before
    assert result[-1]["role"] == "user" and "沒有住院" in result[-1]["content"]
    assert all(set(message) == {"role", "content"} for message in result)
    assert all(message["role"] in {"user", "assistant"} and isinstance(message["content"], str) for message in result)
    for forbidden in ("王小明", "0912345678", "private-case-id", "UPLOAD-CANARY", "private-message-id"):
        assert forbidden not in repr(result)


@pytest.mark.parametrize("response_type", ["answer", "uncertain"])
def test_document_turns_are_removed_using_the_real_paired_response_shape(response_type):
    history = [user("DOCUMENT-USER-CANARY：診斷書逐字內容"),
               assistant("DOCUMENT-ASSISTANT-CANARY", response_type),
               user("我出車禍了"), assistant("請問有沒有住院？")]
    result = privacy().prepare_dialogue(history, "沒有住院")
    assert "DOCUMENT" not in repr(result)
    assert [message["content"] for message in result] == ["我出車禍了", "請問有沒有住院？", "沒有住院"]


@pytest.mark.parametrize("location", ["user", "assistant", "response"])
def test_document_ids_exclude_the_whole_turn_even_if_response_claims_to_be_intake(location):
    first, second = user("DOCUMENT-USER-CANARY"), assistant("DOCUMENT-ASSISTANT-CANARY")
    if location == "response":
        second["response"]["document_id"] = "synthetic-document"
    else:
        (first if location == "user" else second)["document_id"] = "synthetic-document"
    result = privacy().prepare_dialogue([first, second], "沒有住院")
    assert result == [{"role": "user", "content": "沒有住院"}]


@pytest.mark.parametrize("response", [None, "clarification", {}, {"response_type": "unknown"},
                                      {"response_type": []}, {"response_type": {}}, {"response_type": True}])
def test_unclassified_assistant_turns_are_not_used_as_intake(response):
    history = [user("UNCLASSIFIED-USER-CANARY"),
               {"role": "assistant", "content": "UNCLASSIFIED-ASSISTANT-CANARY", "response": response}]
    assert privacy().prepare_dialogue(history, "沒有住院") == [{"role": "user", "content": "沒有住院"}]


def test_legacy_unpaired_users_are_preserved_without_promoting_unknown_roles_or_objects():
    history = [user("車禍"), user("沒有住院"), {"role": "system", "content": "SYSTEM-CANARY"},
               {"role": "tool", "content": "TOOL-CANARY"}, None, user({"ocr": "OBJECT-CANARY"}),
               user(" ")]
    assert privacy().prepare_dialogue(history, "有去急診") == [
        {"role": "user", "content": "車禍"}, {"role": "user", "content": "沒有住院"},
        {"role": "user", "content": "有去急診"}]


def test_only_the_last_assistant_is_retained_and_a_later_document_reply_does_not_restore_an_older_one():
    history = [user("第一次事故描述"), assistant("OLD-ASSISTANT-CANARY"),
               user("沒有住院"), assistant("請問曾到急診或門診就醫嗎？", "claim_suggestion")]
    result = privacy().prepare_dialogue(history, "有去急診")
    assert sum(message["role"] == "assistant" for message in result) == 1
    assert "OLD-ASSISTANT-CANARY" not in repr(result)
    history.extend([user("DOCUMENT-USER-CANARY"), assistant("DOCUMENT-ASSISTANT-CANARY", "answer")])
    result = privacy().prepare_dialogue(history, "目前沒有住院")
    assert not any(message["role"] == "assistant" for message in result)
    assert "DOCUMENT" not in repr(result)


@pytest.mark.parametrize("short_answer", ["有", "沒有", "是", "不是"])
def test_short_answers_keep_their_verified_previous_question_as_well_as_the_latest_question(short_answer):
    history = [user("車禍"), assistant("請問這次有住院嗎？"),
               user(short_answer), assistant("請問有到門診或急診嗎？")]
    assert privacy().prepare_dialogue(history, "有") == [
        {"role": "user", "content": "車禍"},
        {"role": "assistant", "content": "請問這次有住院嗎？"},
        {"role": "user", "content": short_answer},
        {"role": "assistant", "content": "請問有到門診或急診嗎？"},
        {"role": "user", "content": "有"}]


def test_an_old_document_answer_is_not_restored_as_short_answer_context():
    history = [user("DOCUMENT-USER-CANARY"), assistant("DOCUMENT-ANSWER-CANARY", "answer"),
               user("沒有"), assistant("請描述本次情況？")]
    result = privacy().prepare_dialogue(history, "車禍")
    assert "DOCUMENT" not in repr(result)
    assert sum(message["role"] == "assistant" for message in result) == 1


def test_a_short_answer_is_dropped_if_the_history_limit_omits_its_required_question():
    history = [user("車禍"), assistant("請問有住院嗎？"), user("沒有")]
    history.extend(user(f"其他描述{index}") for index in range(7))
    result = privacy().prepare_dialogue(history, "目前只有門診")
    assert len(result) <= 9
    assert not any(message["content"] == "沒有" for message in result)


def test_a_short_answer_is_dropped_if_its_question_is_reduced_to_an_unrelated_tail():
    history = [user("車禍"), assistant("請問這次有住院嗎？" + "甲" * 600 + "。資料準備提示。"),
               user("沒有"), assistant("請問有到門診嗎？")]
    result = privacy().prepare_dialogue(history, "有")
    assert not any(message["content"] == "沒有" for message in result)


def test_an_orphan_or_unstructured_assistant_is_never_forwarded():
    history = [assistant("ORPHAN-CANARY"), user("車禍"),
               {"role": "assistant", "content": "LEGACY-ASSISTANT-CANARY"}]
    assert privacy().prepare_dialogue(history, "沒有住院") == [{"role": "user", "content": "沒有住院"}]


def test_only_the_newest_eight_history_messages_are_kept_in_order():
    history = [user(f"事故描述{index}") for index in range(11)]
    result = privacy().prepare_dialogue(history, "目前沒有住院")
    assert [message["content"] for message in result] == [
        "事故描述3", "事故描述4", "事故描述5", "事故描述6", "事故描述7", "事故描述8",
        "事故描述9", "事故描述10", "目前沒有住院"]


def test_total_budget_prioritizes_the_complete_current_message_then_recent_history():
    current = "本" * 3994 + "沒有住院更正"
    assert len(current) == 4000
    history = [user(character * 1000) for character in "甲乙丙丁戊己庚辛"]
    result = privacy().prepare_dialogue(history, current)
    assert result[-1] == {"role": "user", "content": current}
    assert sum(len(message["content"]) for message in result) == 6000
    assert [message["content"] for message in result[:-1]] == ["庚" * 1000, "辛" * 1000]
    assert len(result) <= 9
    assert all(len(message["content"]) <= 1000 for message in result[:-1] if message["role"] == "user")


def test_history_role_caps_keep_recent_corrections_and_redact_before_slicing():
    history = [user("前" * 993 + "A123456789" + "，更正沒有住院"),
               assistant("前" * 593 + "B223456789" + "，請問是否到過急診？")]
    result = privacy().prepare_dialogue(history, "只有門診")
    assert len(result[0]["content"]) <= 1000
    assert len(result[1]["content"]) <= 600
    assert "更正沒有住院" in result[0]["content"]
    assert "是否到過急診" in result[1]["content"]
    assert "A123" not in repr(result) and "B223" not in repr(result)


def test_mixed_roles_still_obey_the_aggregate_budget_and_history_count():
    history = [entry for index in range(10)
               for entry in (user("事" * 1100 + f"最新{index}"), assistant("問" * 700 + "是否就醫？"))]
    result = privacy().prepare_dialogue(history, "現" * 4000)
    assert result[-1]["content"] == "現" * 4000
    assert len(result) <= 9 and sum(len(message["content"]) for message in result) <= 6000
    assert sum(message["role"] == "assistant" for message in result) <= 1


def test_identifiers_crossing_the_history_tail_boundary_are_redacted_before_clipping():
    history = [user("A123456789" + "後" * 995), assistant("B223456789" + "後" * 595)]
    result = privacy().prepare_dialogue(history, "沒有住院")
    assert not any(character.isdigit() for message in result for character in message["content"])


def test_an_overlong_sentence_is_omitted_instead_of_splitting_its_negation():
    result = privacy().prepare_dialogue([user("沒有住院" + "字" * 997)], "只有門診")
    assert result == [{"role": "user", "content": "只有門診"}]


def test_the_aggregate_budget_does_not_split_negation_inside_an_older_sentence():
    history = [user("字" * 299 + "沒有住院" + "字" * 397),
               user("後" * 1000), assistant("問" * 600)]
    result = privacy().prepare_dialogue(history, "本" * 4000)
    assert [message["content"] for message in result] == ["後" * 1000, "問" * 600, "本" * 4000]


@pytest.mark.parametrize("current", ["", " ", "字" * 4001, None, {"raw": "CURRENT-OBJECT-CANARY"}])
def test_invalid_current_input_is_rejected_without_echoing_its_content(current):
    with pytest.raises((TypeError, ValueError)) as caught:
        privacy().prepare_dialogue([], current)
    assert "CURRENT-OBJECT-CANARY" not in str(caught.value)
