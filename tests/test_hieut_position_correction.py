from PIL import Image, ImageDraw

from backend.services.document_service import _correct_hieut_ieung_confusion, _has_hieut_cap_stroke, _swap_hieut_ieung_initial


def test_hieut_ieung_swap_is_independent_of_name_position() -> None:
    # Each syllable is handled by its own Hangul code point. The same swap
    # works whether ㅎ begins, appears inside, or ends a multi-syllable name.
    assert _swap_hieut_ieung_initial("현") == "연"
    assert _swap_hieut_ieung_initial("연") == "현"
    assert _swap_hieut_ieung_initial("하") == "아"
    assert _swap_hieut_ieung_initial("아") == "하"


def test_hieut_cap_rule_accepts_half_width_upper_stroke() -> None:
    # This resembles the compact printed ㅎ cap in '혜': it spans roughly
    # half of the glyph width and is followed by a visible gap.
    image = Image.new("L", (40, 40), 255)
    draw = ImageDraw.Draw(image)
    draw.line((10, 4, 29, 4), fill=0, width=3)
    draw.ellipse((12, 16, 28, 32), outline=0, width=3)
    assert _has_hieut_cap_stroke(image)


def test_hieut_with_ye_stems_corrects_yeo_to_hye() -> None:
    image = Image.new("L", (80, 80), 255)
    draw = ImageDraw.Draw(image)
    draw.line((4, 5, 42, 5), fill=0, width=3)  # compact ㅎ cap
    draw.ellipse((8, 22, 38, 58), outline=0, width=3)
    draw.line((48, 18, 48, 64), fill=0, width=3)  # ㅖ first stem
    draw.line((66, 18, 66, 64), fill=0, width=3)  # ㅖ second stem
    data = {"text": ["여"], "left": [0], "top": [0], "width": [80], "height": [80]}
    assert _correct_hieut_ieung_confusion(image, "여", data) == "혜"
