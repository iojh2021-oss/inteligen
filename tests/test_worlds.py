from app.worlds import WORLDS


def test_five_worlds_exist():
    assert list(WORLDS) == ["knowledge", "reasoning", "science", "creativity", "learning"]


def test_learning_runs_after_the_other_four():
    assert WORLDS["learning"].depends_on == ("knowledge", "reasoning", "science", "creativity")
    for name in ("knowledge", "reasoning", "science", "creativity"):
        assert WORLDS[name].depends_on == ()
