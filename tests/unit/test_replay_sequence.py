import pytest

from app.modules.proxy.replay_sequence import ReplaySequence


def test_short_replacement_prelude_preserves_downstream_order():
    mapping = ReplaySequence(1)
    mapping.advance(0, suppressed=True)
    assert mapping.advance(1, suppressed=False) == 2
    assert mapping.advance(2, suppressed=False) == 3


def test_full_replacement_prelude_is_suppressed_before_mapping():
    mapping = ReplaySequence(1)
    mapping.advance(0, suppressed=True)
    mapping.advance(1, suppressed=True)
    assert mapping.advance(2, suppressed=False) == 2
    assert mapping.advance(4, suppressed=False) == 4


@pytest.mark.parametrize("bad", [-1, True, None, 0, 1])
def test_replacement_rejects_invalid_or_nonadvancing_sequences(bad):
    mapping = ReplaySequence(1)
    mapping.advance(0, suppressed=True)
    mapping.advance(1, suppressed=True)
    with pytest.raises(ValueError):
        mapping.advance(bad, suppressed=False)
