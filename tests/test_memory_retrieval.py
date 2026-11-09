from app import memory


def test_relevant_ranks_matching_prompt_and_answer(db):
    memory.save("knowledge", "weather and climate definitions", "Climate describes long-term patterns.")
    memory.save("knowledge", "how libraries organize books", "A catalogue helps readers find books.")
    results = memory.relevant("knowledge", "climate patterns", limit=5)
    assert len(results) == 1
    assert results[0]["prompt"] == "weather and climate definitions"


def test_relevant_searches_saved_answers_and_isolates_worlds(db):
    memory.save("science", "paper airplane experiment", "Control the variables and measure flight distance.")
    memory.save("reasoning", "paper airplane experiment", "Discuss the logic of the result.")
    science = memory.relevant("science", "measure flight distance")
    assert len(science) == 1
    assert science[0]["world"] == "science"
    assert memory.relevant("knowledge", "measure flight distance") == []


def test_relevant_supports_unicode_and_empty_queries(db):
    memory.save("knowledge", "آب‌وهوا و اقلیم", "اقلیم الگوهای بلندمدت آب‌وهوا است.")
    assert memory.relevant("knowledge", "اقلیم آب‌وهوا")
    assert memory.relevant("knowledge", " !!! ") == []


def test_relevant_limit_is_bounded_and_forgetting_removes_result(db):
    memory.save("learning", "quality metric", "measure baseline quality")
    memory.save("learning", "quality review", "compare measured quality")
    results = memory.relevant("learning", "quality", limit=1000)
    assert len(results) == 2
    memory.forget(results[0]["id"])
    assert len(memory.relevant("learning", "quality")) == 1
