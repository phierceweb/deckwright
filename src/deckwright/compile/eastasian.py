"""Tell each run carrying CJK which language it is written in, and which face sets it.

A run's ``a:latin`` face has no ideographs, so without ``a:ea`` a renderer picks one of its
own, and without ``lang`` it breaks the line without that language's rules. Kana means
Japanese and hangul Korean; Han characters alone could be Japanese or either Chinese, so
the spec's ``lang:`` decides, or the theme does when it names a face for only one of them.
"""

from __future__ import annotations

from typing import Any

from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

from deckwright.errors import SpecError
from deckwright.utils._cjk import carries_cjk, is_han, is_hangul, is_kana

_TAG = {"ja": "ja-JP", "ko": "ko-KR", "zh-Hans": "zh-CN", "zh-Hant": "zh-TW"}
_HAN_SCRIPTS = ("ja", "zh-Hans", "zh-Hant")
_TRADITIONAL = ("tw", "hk", "mo")
# ISO 639-3 codes for Chinese languages written in Han characters.
_CHINESE = frozenset(
    {
        "zh",
        "cmn",
        "yue",
        "wuu",
        "hak",
        "nan",
        "gan",
        "hsn",
        "cjy",
        "cdo",
        "cpx",
        "czh",
        "czo",
        "mnp",
        "lzh",
    }
)
_AFTER_EA = ("a:cs", "a:sym", "a:hlinkClick", "a:hlinkMouseOver", "a:rtl", "a:extLst")


def script_of(lang: str | None) -> str | None:
    """The ``type.ea`` script a BCP 47 tag is written in, or None for a non-CJK one.

    Read by subtag: ``yue-Hant-HK`` is Traditional by its script, ``zh-TW`` by its region.
    """
    subtags = (lang or "").replace("_", "-").lower().split("-")
    primary, rest = subtags[0], subtags[1:]
    if primary in ("ja", "ko"):
        return primary
    if primary not in _CHINESE:
        return None
    return "zh-Hant" if "hant" in rest or any(r in _TRADITIONAL for r in rest) else "zh-Hans"


def mark_east_asian(slide: Any, *, ea: dict[str, str], lang: str | None, where: str) -> None:
    """Write ``lang`` and ``a:ea`` onto every run on ``slide`` whose text carries CJK.

    A paragraph is judged whole, so a link splitting a Japanese line into runs stays Japanese.

    Raises:
        SpecError: a paragraph carries Han characters and no kana or hangul, no ``lang:``
            names a CJK language, and ``ea`` sets the scripts it could be in different faces.
    """
    for paragraph in slide.shapes._spTree.iter(qn("a:p")):
        runs = [(run, _text(run)) for run in paragraph.iterfind(qn("a:r"))]
        whole = "".join(text for _, text in runs)
        if not carries_cjk(whole):
            continue
        tag, face = _marks(whole, ea=ea, lang=lang, where=where)
        for run, text in runs:
            if not carries_cjk(text) or (tag is None and face is None):
                continue
            properties = run.get_or_add_rPr()
            if tag is not None:
                properties.set("lang", tag)
            if face is None:
                continue
            for old in properties.findall(qn("a:ea")):
                properties.remove(old)
            element = parse_xml(f"<a:ea {nsdecls('a')}/>")
            element.set("typeface", face)
            properties.insert_element_before(element, *_AFTER_EA)


def _text(run: Any) -> str:
    node = run.find(qn("a:t"))
    return "" if node is None or node.text is None else node.text


def _marks(
    text: str, *, ea: dict[str, str], lang: str | None, where: str
) -> tuple[str | None, str | None]:
    """The ``lang`` tag and ``a:ea`` face for a paragraph's CJK runs; None where undecided."""
    declared = script_of(lang)
    for script, present in (("ja", is_kana), ("ko", is_hangul)):
        if any(present(ch) for ch in text):
            return (lang if declared == script else _TAG[script]), ea.get(script)
    if declared is not None:
        return lang, ea.get(declared)
    if not any(is_han(ch) for ch in text):
        return None, None
    mapped = [s for s in _HAN_SCRIPTS if s in ea]
    if len(mapped) == 1:
        return _TAG[mapped[0]], ea[mapped[0]]
    faces = {ea[s] for s in mapped}
    if len(faces) <= 1:
        return None, next(iter(faces), None)
    raise SpecError(
        f"{where}: {text!r} carries Han characters and no kana or hangul, so it could be "
        f"Japanese, Simplified or Traditional Chinese, and the theme sets those in different "
        f"faces ({', '.join(f'{s}: {ea[s]}' for s in mapped)}) — say which with 'lang:' on "
        f"the deck or the slide, e.g. lang: zh-Hans"
    )
