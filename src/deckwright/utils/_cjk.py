"""Chinese, Japanese and Korean text: which characters they are, and where a line may break.

Ideographs, kana, hangul and fullwidth forms are drawn on the em square, so one advance
covers every face: across the CJK fonts on a stock macOS install none is wider than 1.0 em,
bar combining marks, which sit on the character before them. Halfwidth katakana is charged
the same: some faces draw it full width. Line-break classes follow W3C
JLREQ and UAX #14, pinned against LibreOffice's renders in ``tests/utils/test_cjk.py``.
"""

from __future__ import annotations

import unicodedata

CJK_EM = 1.0

_BLOCKS = (
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x2E80, 0x2FDF),  # CJK radicals, Kangxi radicals
    (0x3000, 0x303F),  # CJK symbols and punctuation
    (0x3040, 0x30FF),  # Hiragana, Katakana
    (0x3100, 0x312F),  # Bopomofo
    (0x3130, 0x318F),  # Hangul compatibility Jamo
    (0x31F0, 0x31FF),  # Katakana phonetic extensions
    (0x3200, 0x33FF),  # enclosed CJK, CJK compatibility
    (0x3400, 0x4DBF),  # CJK unified ideographs extension A
    (0x4E00, 0x9FFF),  # CJK unified ideographs
    (0xAC00, 0xD7A3),  # Hangul syllables
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
    (0xFE30, 0xFE4F),  # CJK compatibility forms
    (0xFF01, 0xFFDC),  # fullwidth forms, halfwidth katakana and hangul
    (0xFFE0, 0xFFE6),  # fullwidth signs
    (0x20000, 0x3FFFF),  # supplementary ideographic planes
)
_HANGUL = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7A3), (0xFFA0, 0xFFDC))
_KANA = ((0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F))
_HAN = (
    (0x2E80, 0x2FDF),  # radicals
    (0x3005, 0x3007),  # 々 〆 〇
    (0x3021, 0x3029),  # Hangzhou numerals
    (0x3038, 0x303B),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x3FFFF),
)

# JLREQ cl-02, 05-11: closing brackets, full stops and commas, dividing punctuation,
# middle dots, iteration marks, the prolonged sound mark and small kana.
NO_START = frozenset(
    "）〕］｝〉》」』】〙〗〟’”｠»)]}"
    "、。，．,.・：；:;？！?!‼⁇⁈⁉"
    "ヽヾゝゞ々〻ー"
    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶㇰㇱㇲㇳㇴㇵㇶㇷㇸㇹㇺㇻㇼㇽㇾㇿ"
)
# JLREQ cl-01: opening brackets.
NO_END = frozenset("（〔［｛〈《「『【〘〖〝‘“｟«([{")
# Hung past the line's end rather than carried to the next line with the character before.
HANG = frozenset("、。，．")


def _within(ch: str, blocks: tuple[tuple[int, int], ...]) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in blocks)


def is_cjk(ch: str) -> bool:
    """Whether ``ch`` is a CJK character drawn on the em square."""
    return _within(ch, _BLOCKS) and not unicodedata.combining(ch)


def is_hangul(ch: str) -> bool:
    return _within(ch, _HANGUL)


def is_kana(ch: str) -> bool:
    return _within(ch, _KANA)


def is_han(ch: str) -> bool:
    return _within(ch, _HAN)


def carries_cjk(text: str) -> bool:
    return any(is_cjk(ch) for ch in text)


def atoms(text: str) -> list[str]:
    """``text`` cut where a line may break, whitespace kept as atoms of its own.

    Each ideograph, kana and fullwidth character is its own atom; a run of Latin letters or
    of hangul is one, since Korean breaks at spaces. A character that may not start a line
    joins the atom before it, and one that may not end a line joins the atom after it.
    """
    out: list[str] = []
    word = ""
    for ch in text:
        if ch.isspace() and not is_cjk(ch):
            if word:
                out.append(word)
                word = ""
            out.append(ch)
        elif is_cjk(ch) and not is_hangul(ch):
            if word:
                out.append(word)
                word = ""
            out.append(ch)
        else:
            word += ch
    if word:
        out.append(word)
    return _glue(out)


def _glue(pieces: list[str]) -> list[str]:
    glued: list[str] = []
    for piece in pieces:
        if glued and not piece.isspace() and not glued[-1].isspace():
            if piece[0] in NO_START or glued[-1][-1] in NO_END:
                glued[-1] += piece
                continue
        glued.append(piece)
    return glued
