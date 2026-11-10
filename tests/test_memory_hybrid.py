from app import memory


def test_word_form_variants_are_retrieved_by_character_similarity(db):
    memory.save("science", "evaporation cooling experiment", "result A")
    hits = memory.relevant("science", "evaporating")
    assert [h["result"] for h in hits] == ["result A"]


def test_unrelated_experience_is_rejected(db):
    memory.save("science", "evaporation cooling experiment", "result A")
    assert memory.relevant("science", "medieval castle architecture") == []


def test_persian_variants_are_retrieved(db):
    memory.save("knowledge", "صرفه‌جویی آب در خانه", "نتیجه")
    assert memory.relevant("knowledge", "صرفه جویی آب")


def test_other_worlds_experience_is_not_retrieved(db):
    memory.save("science", "water saving plan", "science only")
    assert memory.relevant("knowledge", "water saving plan") == []


def test_exact_duplicates_are_stored_once_but_changed_results_are_kept(db):
    memory.save("knowledge", "same prompt", "same result")
    memory.save("knowledge", "same prompt", "same result")
    memory.save("knowledge", "same prompt", "different result")
    assert memory.stats()["total"] == 2


def test_prune_keeps_newest_experiences_failures_and_all_experiments(db):
    for i in range(8):
        memory.save("knowledge", f"prompt {i}", f"result {i}")
    for i in range(5):
        memory.save("knowledge", f"fail {i}", f"Failed {i}", kind="failure")
    memory.save("learning", "evolution experiment", "verdict", kind="experiment")
    deleted = memory.prune(max_per_world=3, max_failures=2)
    stats = memory.stats()
    assert deleted == 8
    assert stats["by_kind"] == {"experience": 3, "failure": 2, "experiment": 1}
    assert {m["result"] for m in memory.recent(20) if m["kind"] == "experience"} == {
        "result 5", "result 6", "result 7"}
