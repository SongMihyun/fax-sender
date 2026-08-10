from backend.services.document_service import _swap_hieut_ieung_initial


def test_hieut_ieung_swap_is_independent_of_name_position() -> None:
    # Each syllable is handled by its own Hangul code point. The same swap
    # works whether ㅎ begins, appears inside, or ends a multi-syllable name.
    assert _swap_hieut_ieung_initial("현") == "연"
    assert _swap_hieut_ieung_initial("연") == "현"
    assert _swap_hieut_ieung_initial("하") == "아"
    assert _swap_hieut_ieung_initial("아") == "하"
