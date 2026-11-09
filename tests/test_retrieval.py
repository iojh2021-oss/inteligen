from app.retrieval import rank_rows, tokenize


def row(memory_id, prompt, result="answer"):
    return (memory_id, "knowledge", prompt, result, "2026-11-09T00:00:00+00:00", "req")


def test_tokenizer_supports_persian_and_english():
    assert "قطبنما" in tokenize("قطب‌نما چگونه کار می‌کند")
    assert "entropy" in tokenize("Entropy and heat")


def test_bm25_prefers_specific_relevant_prompt():
    rows = [
        row(1, "entropy"),
        row(2, "entropy in thermodynamics and statistical mechanics"),
        row(3, "how to cook pasta"),
    ]
    ranked = rank_rows(rows, "entropy thermodynamics", limit=2)
    assert [item[0] for item in ranked] == [2, 1]


def test_phrase_match_breaks_close_relevance_tie():
    rows = [row(1, "heat and entropy"), row(2, "entropy heat")]
    assert rank_rows(rows, "entropy heat", limit=1)[0][0] == 2


def test_empty_query_and_nonpositive_limit_return_nothing():
    rows = [row(1, "entropy")]
    assert rank_rows(rows, " ") == []
    assert rank_rows(rows, "entropy", limit=0) == []


def test_unmatched_documents_are_not_returned():
    assert rank_rows([row(1, "pasta")], "entropy") == []
