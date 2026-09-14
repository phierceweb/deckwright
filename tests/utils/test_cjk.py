"""CJK measurement and line breaking. Expectations come from LibreOffice renders of the same
strings at 20pt: `。` hangs past the edge, `ー` and small `っ` never start a line, `「` never
ends one, and Korean wraps at spaces. Widths here carry `_MARGIN`, so each box is 10.5 em."""

import pytest

from deckwright.utils._cjk import CJK_EM, atoms, is_cjk
from deckwright.utils.text import text_em, wrapped_lines

_TEN_AND_A_HALF_EM = 10.5 * 20 / 72  # inches at 20pt


def _lines(text: str) -> int:
    return wrapped_lines(text, width_in=_TEN_AND_A_HALF_EM, size_pt=20)


def test_a_cjk_character_is_measured_on_its_em_square_in_any_face():
    assert text_em("日本語", "Calibri") == pytest.approx(3 * 1.04)
    assert text_em("한국어", None) == pytest.approx(3 * 1.04)
    assert CJK_EM == 1.0


def test_a_combining_mark_is_not_a_cjk_character_of_its_own():
    assert is_cjk("あ") and is_cjk("。") and is_cjk("Ａ")
    assert not is_cjk("゙")  # combining voiced sound mark
    assert not is_cjk("A")


def test_closing_punctuation_and_small_kana_join_the_character_before():
    assert atoms("けこ。さ") == ["け", "こ。", "さ"]
    assert atoms("りーさ") == ["りー", "さ"]
    assert atoms("じっさ") == ["じっ", "さ"]


def test_an_opening_bracket_joins_the_character_after():
    assert atoms("く「けこ」さ") == ["く", "「け", "こ」", "さ"]


def test_latin_inside_cjk_moves_as_a_whole_word():
    assert atoms("日本English語") == ["日", "本", "English", "語"]


def test_korean_breaks_at_spaces():
    assert atoms("한국어 문장은") == ["한국어", " ", "문장은"]


def test_a_full_stop_at_the_end_of_a_full_line_hangs_instead_of_carrying_a_character_down():
    """Ten kana then `。`: LibreOffice sets all eleven on one line."""
    assert _lines("あいうえおかきくけこ。") == 1


def test_a_prolonged_sound_mark_carries_the_character_before_it_to_the_next_line():
    """`ー` as the eleventh character takes `り` down, so the second line runs over."""
    assert _lines("あいうえおかきくけりーあいうえおかきくけ") == 3
    assert _lines("あいうえおかきくけりあいうえおかきくけあ") == 2


def test_latin_text_is_wrapped_exactly_as_before():
    assert wrapped_lines("the quick brown fox jumps over", width_in=2, size_pt=18) == 3
    assert wrapped_lines("x" * 20, width_in=2, size_pt=18) == 2


def _cjk_fonts() -> list[str]:
    import shutil
    import subprocess

    if shutil.which("fc-list") is None:
        return []
    out = (
        subprocess.run(
            ["fc-list", ":lang=ja", "file"], capture_output=True, text=True, check=False
        ).stdout
        + subprocess.run(
            ["fc-list", ":lang=ko", "file"], capture_output=True, text=True, check=False
        ).stdout
    )
    return sorted({line.split(":")[0] for line in out.splitlines() if "LastResort" not in line})


_CJK_STRINGS = (
    "日本語の文章は、句読点で区切られます。",
    "「カタカナ」とひらがなが混ざる。",
    "한국어 문장은 띄어쓰기로 나뉩니다.",
    "简体中文的句子，包括标点符号！",
    "繁體中文的句子，包括標點符號！",
    "ＡＢＣ１２３（全角）",
)


@pytest.mark.skipif(not _cjk_fonts(), reason="no CJK font is installed to measure against")
@pytest.mark.parametrize("string", _CJK_STRINGS)
def test_cjk_is_never_measured_narrower_than_any_installed_cjk_font_draws_it(string):
    from PIL import ImageFont

    widths = {}
    for path in _cjk_fonts():
        font = ImageFont.truetype(path, 1000)
        drawable = [ch for ch in string if font.getmask(ch).size != (0, 0) or ch.isspace()]
        if len(drawable) == len(string):
            widths[path] = font.getlength(string) / 1000
    assert widths, "no installed CJK font covers this string"
    assert text_em(string, None) >= max(widths.values())


def test_an_ideographic_space_takes_a_full_em():
    """Eight ideographs and three U+3000 are eleven ems: two lines in ten, where charging each
    space a Poppins space would squeeze them into one."""
    text = "一二　三四　五六　七八"
    assert wrapped_lines(text, width_in=10.5 * 18 / 72, size_pt=18, face="Poppins") == 2


def test_halfwidth_katakana_breaks_between_characters_and_is_measured_as_cjk():
    from deckwright.utils.text import overlong_word

    assert atoms("ｽｶｲ") == ["ｽ", "ｶ", "ｲ"]
    assert overlong_word("ｶﾌﾞｼｷｶﾞｲｼｬｽｶｲﾂﾘｰ", width_in=1.39, size_pt=22) is None


def test_a_korean_word_wider_than_its_line_is_an_overlong_word():
    """Korean breaks at spaces, so a word that cannot fit breaks mid-word like a Latin one."""
    from deckwright.utils.text import overlong_word

    found = overlong_word("대한민국헌법재판소결정문", width_in=1.5, size_pt=18)
    assert found is not None and found[0] == "대한민국헌법재판소결정문"
