from app.worlds import WORLDS

def test_five_worlds_exist():
    assert list(WORLDS) == ["knowledge", "reasoning", "science", "creativity", "learning"]
