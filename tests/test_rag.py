"""Rights Q&A (RAG): exact fee answers, retrieval, refusals and the grounding check."""
import httpx

from app import config, rag


def setup_module():
    config.LLM_PROVIDER = "mock"


def test_fee_answer_uses_government_table():
    r = rag.answer("সৌদি যেতে সরকারি খরচ কত?")
    assert r["mode"] == "fact" and "১,৬৫,০০০" in r["answer"]
    assert r["sources"][0]["id"].startswith("fees#") and r["confidence"] == "high"


def test_overpayment_is_worked_out_banglish():
    r = rag.answer("malaysia te 2 lakh 50 hajar dilam")
    assert r["compare"] == {"country": "মালয়েশিয়া", "cap_bdt": 78990, "paid_bdt": 250000, "over_bdt": 171010}
    assert "১,৭১,০১০" in r["answer"]


def test_comma_grouped_amount_from_the_check_page():
    r = rag.answer("সৌদি আরব যেতে ৪,০০,০০০ টাকা দিয়েছি, বেশি হয়েছে?")
    assert r["mode"] == "fact" and r["compare"]["over_bdt"] == 235000


def test_salary_is_not_mistaken_for_a_fee():
    r = rag.answer("সৌদিতে বেতনের টাকা না দিলে কী করব")
    assert r["mode"] != "fact" and "শ্রম কল্যাণ" in r["answer"]


def test_saudi_women_domestic_workers_zero_cost():
    assert "শূন্য" in rag.answer("নারী গৃহকর্মী সৌদি গেলে কত টাকা লাগে")["answer"]


def test_singapore_has_no_number_because_sources_disagree():
    r = rag.answer("সিঙ্গাপুর যেতে খরচ কত")
    assert "একমত নয়" in r["answer"] and "১,৬৫,০০০" not in r["answer"]


def test_off_topic_is_refused():
    for q in ["ক্রিকেট খেলার নিয়ম কী?", "পদ্মা সেতু কবে খুলেছে", "best smartphone under 20000"]:
        r = rag.answer(q)
        assert r["mode"] == "no_match" and r["sources"] == [] and r["actions"][0]["href"] == "tel:16135"


def test_answers_cite_and_offer_the_right_call_button():
    r = rag.answer("বিনা টাকায় উকিল কোথায় পাব?")
    assert "১৬৬৯৯" in r["answer"] and "[1]" in r["answer"]
    assert any(a["href"] == "tel:16699" for a in r["actions"])


def test_grounding_check_rejects_invented_numbers():
    hits = rag.search("সালিশে টাকা ফেরত পেতে কত দিন লাগে")
    for n, h in enumerate(hits, 1):
        h["n"] = n
    assert rag.grounding_problems("সাধারণত অন্তত চার মাস লাগে [1]।", hits) == []
    assert rag.grounding_problems("সালিশে ৪৫ দিন লাগে [1]।", hits)          # 45 is not in the passages
    assert rag.grounding_problems("সালিশে সময় লাগে [9]।", hits)           # cites a passage that does not exist
    assert rag.grounding_problems("সালিশে সময় লাগে।", hits)               # no citation


def test_ai_answer_with_invented_number_falls_back(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "x")
    monkeypatch.setattr(config, "RAG_GENERATE", True)

    def fake(text):
        return lambda url, json=None, **k: httpx.Response(
            200, json={"choices": [{"message": {"content": text}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake("প্রবাসবন্ধুর নম্বর ১৬১৩৫ [1]। (আইনি তথ্য, আইনি পরামর্শ নয়।)"))
    assert rag.answer("প্রবাসবন্ধু নম্বর কত")["mode"] == "generated"
    monkeypatch.setattr(httpx, "post", fake("প্রবাসবন্ধুর নম্বর ১৬২২২ [1]।"))
    r = rag.answer("প্রবাসবন্ধু নম্বর কত")
    assert r["mode"] == "extractive" and "grounding check" in r["note"] and "১৬১৩৫" in r["answer"]
