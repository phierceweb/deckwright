"""Validate OOXML against the ISO/IEC 29500-4:2016 schemas vendored in ``tests/schemas/ooxml/``.
What a verdict covers, and what it records beside it, is in ``docs/testing.md``."""

from __future__ import annotations

import copy
import dataclasses
import functools
import hashlib
import io
import pathlib
import re
import zipfile
from typing import Any

from lxml import etree

SCHEMAS = pathlib.Path(__file__).parent / "schemas" / "ooxml"
PML = "http://schemas.openxmlformats.org/presentationml/2006/main"
DML = "http://schemas.openxmlformats.org/drawingml/2006/main"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
DIAGRAM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
OMML = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WML = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE = "application/vnd.openxmlformats-officedocument."
CONTENT_TYPES_PART = "[Content_Types].xml"
NO_NAMESPACE = "(no namespace)"
_XSD = "http://www.w3.org/2001/XMLSchema"
_ALTERNATE, _CHOICE, _FALLBACK = (
    f"{{{MC}}}{n}" for n in ("AlternateContent", "Choice", "Fallback")
)
_MC_ATTRIBUTES = frozenset(
    f"{{{MC}}}{n}" for n in ("Ignorable", "ProcessContent", "MustUnderstand")
)
_IGNORABLE_ATTRIBUTE = f"{{{MC}}}Ignorable"
_PACKAGE = "application/vnd.openxmlformats-package."
_PRESENTATIONML = f"{OFFICE}presentationml."
_MACRO = "application/vnd.ms-powerpoint."
_GENERIC_XML = ("application/xml", "text/xml")
_XML_WITHOUT_SUFFIX = (f"{OFFICE}vmldrawing",)
_ENCODINGS = ("utf-8", "utf-16")
_LINE = re.compile(r"line \d+ ")
# Slides and what hangs off them: the build's own, whatever the template held.
_BUILDS_OWN = re.compile(r"^ppt/(slides|notesSlides|charts)/")

#: The package's own parts, whose roots no vendored schema declares.
PACKAGE_ROOTS = frozenset(
    {
        f"{{{CONTENT_TYPES}}}Types",
        "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships",
        "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}coreProperties",
        "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Properties",
    }
)

# The one attribute wml.xsd takes from ../mce/mc.xsd, which is not vendored (SOURCE.md).
_IGNORABLE = (
    b'<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
    b'targetNamespace="http://schemas.openxmlformats.org/markup-compatibility/2006">'
    b'<xsd:attribute name="Ignorable" type="xsd:string"/></xsd:schema>'
)


class _Ignorable(etree.Resolver):
    def resolve(self, url, pubid, context):
        if url.endswith("mce/mc.xsd"):
            return self.resolve_string(_IGNORABLE, context)
        return None


@functools.cache
def schema(entry: str = "pml.xsd") -> etree.XMLSchema:
    """The schema compiled from ``entry`` and everything it imports."""
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(_Ignorable())
    return etree.XMLSchema(etree.parse(str(SCHEMAS / entry), parser))


def _closure(entry: str) -> list[pathlib.Path]:
    seen: list[pathlib.Path] = []
    todo = [SCHEMAS / entry]
    while todo:
        path = todo.pop().resolve()
        if path in seen or not path.is_file():
            continue
        seen.append(path)
        root = etree.parse(str(path)).getroot()
        for ref in root.iter(f"{{{_XSD}}}import", f"{{{_XSD}}}include"):
            if ref.get("schemaLocation"):
                todo.append(path.parent / ref.get("schemaLocation"))
    return seen


@functools.cache
def declared_roots(entry: str = "pml.xsd") -> frozenset[str]:
    """Every global element the closure of ``entry`` declares, as ``{namespace}name``."""
    roots = set()
    for path in _closure(entry):
        root = etree.parse(str(path)).getroot()
        namespace = root.get("targetNamespace")
        for element in root.findall(f"{{{_XSD}}}element"):
            roots.add(f"{{{namespace}}}{element.get('name')}")
    return frozenset(roots)


@functools.cache
def understood() -> frozenset[str]:
    """The namespaces a verdict on a part judges: what ``pml.xsd`` reaches, Office Math, and
    markup compatibility. WordprocessingML arrives only through the math schema."""
    reached = {
        etree.parse(str(path)).getroot().get("targetNamespace") for path in _closure("pml.xsd")
    }
    return frozenset(reached | {OMML, MC})


_PRESENTATION = f"{{{PML}}}presentation"
#: The root a part must carry, by its content type in lower case.
EXPECTED_ROOT = {
    f"{_PRESENTATIONML}presentation.main+xml": _PRESENTATION,
    f"{_PRESENTATIONML}template.main+xml": _PRESENTATION,
    f"{_PRESENTATIONML}slideshow.main+xml": _PRESENTATION,
    f"{_MACRO}presentation.macroenabled.main+xml": _PRESENTATION,
    f"{_MACRO}template.macroenabled.main+xml": _PRESENTATION,
    f"{_MACRO}slideshow.macroenabled.main+xml": _PRESENTATION,
    f"{_MACRO}addin.macroenabled.main+xml": _PRESENTATION,
    f"{_PRESENTATIONML}slide+xml": f"{{{PML}}}sld",
    f"{_PRESENTATIONML}slidelayout+xml": f"{{{PML}}}sldLayout",
    f"{_PRESENTATIONML}slidemaster+xml": f"{{{PML}}}sldMaster",
    f"{_PRESENTATIONML}notesslide+xml": f"{{{PML}}}notes",
    f"{_PRESENTATIONML}notesmaster+xml": f"{{{PML}}}notesMaster",
    f"{_PRESENTATIONML}handoutmaster+xml": f"{{{PML}}}handoutMaster",
    f"{_PRESENTATIONML}presprops+xml": f"{{{PML}}}presentationPr",
    f"{_PRESENTATIONML}viewprops+xml": f"{{{PML}}}viewPr",
    f"{_PRESENTATIONML}tablestyles+xml": f"{{{DML}}}tblStyleLst",
    f"{_PRESENTATIONML}tags+xml": f"{{{PML}}}tagLst",
    f"{_PRESENTATIONML}commentauthors+xml": f"{{{PML}}}cmAuthorLst",
    f"{_PRESENTATIONML}comments+xml": f"{{{PML}}}cmLst",
    f"{_PRESENTATIONML}slideupdateinfo+xml": f"{{{PML}}}sldSyncPr",
    f"{OFFICE}theme+xml": f"{{{DML}}}theme",
    f"{OFFICE}themeoverride+xml": f"{{{DML}}}themeOverride",
    f"{OFFICE}thememanager+xml": f"{{{DML}}}themeManager",
    f"{OFFICE}drawingml.chart+xml": f"{{{CHART}}}chartSpace",
    f"{OFFICE}drawingml.chartshapes+xml": f"{{{CHART}}}userShapes",
    f"{OFFICE}drawingml.diagramdata+xml": f"{{{DIAGRAM}}}dataModel",
    f"{OFFICE}drawingml.diagramlayout+xml": f"{{{DIAGRAM}}}layoutDef",
    f"{OFFICE}drawingml.diagramstyle+xml": f"{{{DIAGRAM}}}styleDef",
    f"{OFFICE}drawingml.diagramcolors+xml": f"{{{DIAGRAM}}}colorsDef",
    f"{_PACKAGE}relationships+xml": (
        "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships"
    ),
    f"{_PACKAGE}core-properties+xml": (
        "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}coreProperties"
    ),
    f"{OFFICE}extended-properties+xml": (
        "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Properties"
    ),
    f"{OFFICE}custom-properties+xml": (
        "{http://schemas.openxmlformats.org/officeDocument/2006/custom-properties}Properties"
    ),
}
_OWNED_ROOTS = frozenset(EXPECTED_ROOT.values())


def _parser(**options: Any) -> etree.XMLParser:
    # libxml2's default depth and size limits stand; a part past them is a fault.
    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, **options)


def _required(choice: Any) -> set[str]:
    """The namespaces a Choice ``Requires``, resolved while it is still attached: a detached
    subtree keeps only the declarations it uses, under the prefixes it uses."""
    prefixes = choice.get("Requires", "").split()
    return {ns for ns in (choice.nsmap.get(p) for p in prefixes) if ns}


def _ignorable(element: Any) -> set[str]:
    """The namespaces ``element``'s own ``mc:Ignorable`` names."""
    prefixes = element.get(_IGNORABLE_ATTRIBUTE, "").split()
    return {ns for ns in (element.nsmap.get(p) for p in prefixes) if ns}


def _attach(parent: Any, index: int, text: str | None) -> None:
    """Put ``text`` where ``parent``'s ``index``-th child would begin."""
    if not text:
        return
    if index == 0:
        parent.text = (parent.text or "") + text
    else:
        before = parent[index - 1]
        before.tail = (before.tail or "") + text


def _drop(element: Any) -> None:
    """Remove ``element``, leaving the text after it where it stood."""
    parent = element.getparent()
    _attach(parent, parent.index(element), element.tail)
    parent.remove(element)


def branch(root: Any, which: str, index: int = 0) -> Any:
    """A copy with every ``mc:AlternateContent`` replaced by its ``"Fallback"`` or its
    ``index``-th ``"Choice"`` (the first where it has fewer), less what that Choice ``Requires``."""
    assert which in ("Choice", "Fallback"), which
    tree = copy.deepcopy(root)
    while (alternate := tree.find(f".//{_ALTERNATE}")) is not None:
        if which == "Choice":
            options = alternate.findall(_CHOICE)
            chosen = (options[index] if index < len(options) else options[0]) if options else None
        else:
            chosen = alternate.find(_FALLBACK)
        children: list[Any] = []
        text = None
        if chosen is not None:
            required = _required(chosen)
            for el in list(chosen.iter(tag=etree.Element)):
                if el is chosen or el.getparent() is None:
                    continue
                if etree.QName(el).namespace in required:
                    _drop(el)
                    continue
                for name in [n for n in el.attrib if etree.QName(n).namespace in required]:
                    del el.attrib[name]
            children, text = list(chosen), chosen.text
        parent = alternate.getparent()
        at = parent.index(alternate)
        tail = alternate.tail
        parent.remove(alternate)
        _attach(parent, at, text)
        for offset, child in enumerate(children):
            parent.insert(at + offset, child)
        _attach(parent, at + len(children), tail)
    return tree


def _without_ignorable(tree: Any) -> Any:
    """``tree``, in place, less what an ``mc:Ignorable`` lets a reader skip and less the
    markup-compatibility attributes themselves."""
    for el in list(tree.iter(tag=etree.Element)):
        skipped = _ignorable(el) - understood()
        for inner in list(el.iter(tag=etree.Element)) if skipped else ():
            if inner is not el and inner.getparent() is not None:
                if etree.QName(inner).namespace in skipped:
                    _drop(inner)
                    continue
            for name in [n for n in inner.attrib if etree.QName(n).namespace in skipped]:
                del inner.attrib[name]
        for name in [n for n in el.attrib if n in _MC_ATTRIBUTES]:
            del el.attrib[name]
    return tree


def views(root: Any) -> list[tuple[str, Any]]:
    """The part as each reader sees it, less what an ``mc:Ignorable`` lets it skip: one view
    per Choice position, then the Fallback, every wrapper taking the same branch."""
    base = _without_ignorable(copy.deepcopy(root))
    wrappers = list(base.iter(_ALTERNATE))
    if not wrappers:
        return [("", base)]
    width = max(len(w.findall(_CHOICE)) for w in wrappers)
    labels = ["[Choice] "] + [f"[Choice {k + 1}] " for k in range(1, width)]
    out = [(label, branch(base, "Choice", k)) for k, label in enumerate(labels)]
    out.append(("[Fallback] ", branch(base, "Fallback")))
    return out


def unsigned_axis_ids(chart_space: Any) -> Any:
    """A copy with a negative ``val`` on ``c:axId`` and ``c:crossAx`` made unsigned, which
    python-pptx writes signed; any other value is left for the schema to name."""
    checked = copy.deepcopy(chart_space)
    for ax_id in checked.iter(f"{{{CHART}}}axId", f"{{{CHART}}}crossAx"):
        val = ax_id.get("val", "")
        if re.fullmatch(r"-[0-9]+", val):
            ax_id.set("val", val[1:])
    return checked


def percent_bullet_sizes(root: Any) -> Any:
    """A copy with each ``a:buSzPct`` PowerPoint writes in thousandths of a whole percent
    rewritten as the ``N%`` the schema wants; any other value is left for the schema to name."""
    checked = copy.deepcopy(root)
    for size in checked.iter(f"{{{DML}}}buSzPct"):
        val = size.get("val", "")
        if re.fullmatch(r"[0-9]+", val) and int(val) % 1000 == 0:
            size.set("val", f"{int(val) // 1000}%")
    return checked


def _messages(label: str, log: Any) -> list[str]:
    return [f"{label}line {e.line} at {e.path}: {e.message}" for e in log]


def _prefixes(element: Any, attribute: str) -> list[tuple[str, str | None]]:
    return [(p, element.nsmap.get(p)) for p in element.get(attribute, "").split()]


def _mce_errors(root: Any) -> list[str]:
    """Markup compatibility no view can judge (``docs/testing.md``)."""
    errors = []
    must, process = f"{{{MC}}}MustUnderstand", f"{{{MC}}}ProcessContent"
    for element in root.iter(tag=etree.Element):
        for attribute in (_IGNORABLE_ATTRIBUTE, must, process):
            for prefix, namespace in _prefixes(element, attribute):
                name = etree.QName(attribute).localname
                if namespace is None:
                    errors.append(f"[mc] {name} names the undeclared prefix {prefix!r}")
                elif attribute == must and namespace not in understood():
                    errors.append(
                        f"[mc] MustUnderstand names {namespace}, which no schema here has"
                    )
                elif attribute == process and not any(
                    namespace in _ignorable(h) for h in [element, *element.iterancestors()]
                ):
                    errors.append(f"[mc] ProcessContent names {namespace}, which nothing ignores")
        tag = element.tag
        if etree.QName(element).namespace == MC and tag not in (_ALTERNATE, _CHOICE, _FALLBACK):
            errors.append(
                f"[mc] {etree.QName(element).localname} is no markup-compatibility element"
            )
        parent = element.getparent()
        if tag in (_CHOICE, _FALLBACK) and (parent is None or parent.tag != _ALTERNATE):
            errors.append(f"[mc] {etree.QName(element).localname} outside an AlternateContent")
    for alternate in root.iter(_ALTERNATE):
        children = [c.tag for c in alternate if isinstance(c.tag, str)]
        choices = children.count(_CHOICE)
        stray = (alternate.text or "").strip() or any((c.tail or "").strip() for c in alternate)
        shaped = children == [_CHOICE] * choices + [_FALLBACK] * (len(children) - choices)
        if choices < 1 or len(children) - choices > 1 or not shaped or stray:
            errors.append(
                "[mc] AlternateContent is not one or more Choice then at most one Fallback"
            )
        for element in [alternate, *alternate.findall(_CHOICE), *alternate.findall(_FALLBACK)]:
            allowed = {"Requires"} if element.tag == _CHOICE else set()
            for name in element.attrib:
                if name not in allowed and name not in _MC_ATTRIBUTES:
                    errors.append(f"[mc] {etree.QName(element).localname} carries attribute {name}")
        for choice in alternate.findall(_CHOICE):
            prefixes = _prefixes(choice, "Requires")
            if not prefixes:
                errors.append("[mc] Choice with no Requires")
            for prefix, namespace in prefixes:
                if namespace is None:
                    errors.append(f"[mc] Requires names the undeclared prefix {prefix!r}")
                elif namespace in understood():
                    errors.append(
                        f"[mc] Requires names {namespace}, which every reader understands"
                    )
    return errors


# The smallest global DrawingML element a run can sit in, for judging a run's properties.
_RUN_HOST = (
    f'<a:tbl xmlns:a="{DML}"><a:tblGrid><a:gridCol w="1"/></a:tblGrid><a:tr h="1"><a:tc>'
    "<a:txBody><a:bodyPr/><a:p><a:r><a:t>x</a:t></a:r></a:p></a:txBody></a:tc></a:tr></a:tbl>"
)


def _maths(root: Any) -> list[Any]:
    """Every Office Math element whose parent is not Office Math: each one judged on its own."""
    return [
        el
        for el in root.iter(tag=etree.Element)
        if etree.QName(el).namespace == OMML
        and (el.getparent() is None or etree.QName(el.getparent()).namespace != OMML)
    ]


def _math_errors(root: Any) -> list[str]:
    """Office Math against ``shared-math.xsd``, each DrawingML ``a:rPr`` in it standing in the
    slot Word's ``w:rPr`` has, and judged against ``pml.xsd`` in a run of its own."""
    xsd, dml = schema("shared-math.xsd"), schema()
    errors = []
    for n, element in enumerate(_maths(root), start=1):
        checked = copy.deepcopy(element)
        for word in checked.iter(f"{{{WML}}}*"):
            errors.append(f"[math {n}] {etree.QName(word).localname} is WordprocessingML")
        for m, props in enumerate(list(checked.iter(f"{{{DML}}}rPr")), start=1):
            host = etree.fromstring(_RUN_HOST)
            host.find(f".//{{{DML}}}r").insert(0, copy.deepcopy(props))
            if not dml.validate(host):
                errors += _messages(f"[math {n} rPr {m}] ", dml.error_log)
            props.addprevious(etree.Element(f"{{{WML}}}rPr"))
            props.getparent().remove(props)
        if not xsd.validate(checked):
            errors += _messages(f"[math {n}] ", xsd.error_log)
    return errors


def validate(root: Any, xsd: etree.XMLSchema | None = None) -> list[str]:
    """What the schemas find in ``root``: each view of its markup compatibility, its wrappers
    and its Office Math, after the rewrites ``docs/testing.md`` names."""
    xsd = xsd or schema()
    if etree.QName(root).text == f"{{{CHART}}}chartSpace":
        root = unsigned_axis_ids(root)
    root = percent_bullet_sizes(root)
    errors = []
    for label, tree in views(root):
        if not xsd.validate(tree):
            errors += _messages(label, xsd.error_log)
    return errors + _mce_errors(root) + _math_errors(root)


def _skipped_by_a_reader(element: Any) -> bool:
    """Whether some reader's view drops ``element``: an ancestor is in a namespace an enclosing
    Choice ``Requires``, or one an ``mc:Ignorable`` above it names."""
    for ancestor in element.iterancestors():
        namespace = etree.QName(ancestor).namespace
        if any(namespace in _required(c) for c in ancestor.iterancestors(_CHOICE)):
            return True
        if any(namespace in _ignorable(h) for h in [ancestor, *ancestor.iterancestors()]):
            return True
    return False


def _effective_parent(element: Any) -> Any:
    """``element``'s parent once every markup-compatibility element is resolved."""
    parent = element.getparent()
    while parent is not None and etree.QName(parent).namespace == MC:
        parent = parent.getparent()
    return parent


def unjudged(root: Any) -> tuple[frozenset[str], frozenset[str]]:
    """``(namespaces, tags)`` a verdict on ``root`` passed over (``docs/testing.md``)."""
    roots = declared_roots()
    namespaces: set[str] = set()
    tags: set[str] = set()
    for el in root.iter(tag=etree.Element):
        tag = etree.QName(el)
        if tag.namespace is None:
            namespaces.add(NO_NAMESPACE)
        elif tag.namespace not in understood():
            namespaces.add(tag.namespace)
        for name in el.attrib:
            namespace = etree.QName(name).namespace
            if namespace and namespace not in understood():
                namespaces.add(namespace)
        parent = _effective_parent(el)
        if parent is None or tag.namespace not in understood() or tag.namespace == MC:
            continue
        parent_tag = etree.QName(parent)
        if tag.namespace == OMML and parent_tag.namespace != OMML:
            continue
        foreign_parent = parent_tag.namespace not in understood()
        grandparent = _effective_parent(parent)
        in_extension = (
            parent_tag.localname == "ext"
            and grandparent is not None
            and etree.QName(grandparent).localname == "extLst"
        )
        if foreign_parent and _skipped_by_a_reader(el):
            tags.add(tag.text)
        elif (foreign_parent or in_extension) and tag.text not in roots:
            tags.add(tag.text)
    return frozenset(namespaces), frozenset(tags)


def assert_chart_valid(chart_space: Any) -> None:
    """Fail with every error ``validate`` finds in a ``c:chartSpace``."""
    errors = validate(chart_space)
    assert errors == [], errors


def canonical(root: Any) -> bytes:
    """``root`` with blank text between elements dropped, as python-pptx reads a part, in
    canonical form; as serialised, where libxml2 refuses to canonicalise it."""
    tidy = etree.fromstring(etree.tostring(root), _parser(remove_blank_text=True))
    try:
        return etree.tostring(tidy, method="c14n", with_comments=False)
    except etree.C14NError:
        return etree.tostring(tidy)


@dataclasses.dataclass(frozen=True)
class DeckReport:
    """Every XML part of one deck, sorted by what the schemas could say about it."""

    valid: tuple[str, ...]
    invalid: dict[str, tuple[str, ...]]
    unchecked: dict[str, str]
    passed_over: dict[str, tuple[str, ...]]
    unreached: dict[str, tuple[str, ...]]
    digests: dict[str, str]

    def split(
        self, source: DeckReport
    ) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
        """``(own, inherited)``: a fault is the template's only in a part carried over from
        ``source`` with its digest and its errors (``docs/testing.md``)."""
        own: dict[str, tuple[str, ...]] = {}
        inherited: dict[str, tuple[str, ...]] = {}
        for part, errors in self.invalid.items():
            unchanged = part in self.digests and self.digests[part] == source.digests.get(part)
            mine = sorted(_LINE.sub("", e) for e in errors)
            theirs = sorted(_LINE.sub("", e) for e in source.invalid.get(part, ()))
            carried = not _BUILDS_OWN.match(part) and unchanged and mine == theirs
            (inherited if carried else own)[part] = errors
        return own, inherited


def _package(archive: zipfile.ZipFile) -> tuple[dict[str, str | None], dict[str, list[str]]]:
    """Each part named ``.xml`` or ``.rels``, typed XML, or untyped, with its content type
    (``None`` where the package declares none); and the package's faults, by part."""
    faults: dict[str, list[str]] = {}
    names = [n for n in archive.namelist() if not n.endswith("/")]
    member = next((n for n in names if n.lower() == CONTENT_TYPES_PART.lower()), None)
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    if member is None:
        faults[CONTENT_TYPES_PART] = ["absent from the package"]
    else:
        try:
            types = etree.fromstring(archive.read(member), _parser())
        except etree.LxmlError as exc:
            faults[member] = [f"{type(exc).__name__}: {exc}"]
        else:
            for entry in types.iter(f"{{{CONTENT_TYPES}}}Default", f"{{{CONTENT_TYPES}}}Override"):
                kind = etree.QName(entry).localname
                table = defaults if kind == "Default" else overrides
                key = (entry.get("Extension") or entry.get("PartName") or "").lower()
                if key in table:
                    faults.setdefault(member, []).append(f"{kind} for {key!r} appears twice")
                table[key] = (entry.get("ContentType") or "").lower()
    by_folded: dict[str, list[str]] = {}
    for name in names:
        by_folded.setdefault(name.lower(), []).append(name)
    for twins in by_folded.values():
        if len(twins) > 1:
            for twin in set(twins):
                others = sorted(set(twins) - {twin})
                fault = (
                    f"differs only in case from {others}"
                    if others
                    else "appears twice in the archive"
                )
                faults.setdefault(twin, []).append(fault)
    parts: dict[str, str | None] = {}
    for part in dict.fromkeys(names):
        if part == member:
            ctype: str | None = _GENERIC_XML[0]
        else:
            key = "/" + part.lower()
            extension = part.rsplit(".", 1)[-1].lower() if "." in part else ""
            ctype = (overrides[key] if key in overrides else defaults.get(extension)) or None
        declared_xml = ctype is not None and (
            ctype.endswith("+xml") or ctype in _GENERIC_XML or ctype in _XML_WITHOUT_SUFFIX
        )
        if declared_xml or ctype is None or part.lower().endswith((".xml", ".rels")):
            parts[part] = ctype
    return parts, faults


def validate_deck(deck: str | pathlib.Path) -> DeckReport:
    """Validate every XML part of ``deck`` whose root the vendored schemas declare, listing
    the rest unchecked and faulting what cannot be judged (``docs/testing.md``)."""
    xsd, roots = schema(), declared_roots()
    valid: list[str] = []
    invalid: dict[str, tuple[str, ...]] = {}
    unchecked: dict[str, str] = {}
    over: dict[str, tuple[str, ...]] = {}
    unreached: dict[str, tuple[str, ...]] = {}
    digests: dict[str, str] = {}
    with zipfile.ZipFile(deck) as archive:
        parts, faults = _package(archive)
        invalid.update({part: tuple(found) for part, found in faults.items()})
        for part, ctype in parts.items():
            if part in invalid:
                continue
            if ctype is None:
                invalid[part] = ("no content type in [Content_Types].xml",)
                continue
            try:
                root = etree.fromstring(archive.read(part), _parser())
            except etree.LxmlError as exc:
                invalid[part] = (f"{type(exc).__name__}: {exc}",)
                continue
            info = root.getroottree().docinfo
            if info.doctype:
                invalid[part] = ("a DOCTYPE, which OPC forbids",)
                continue
            if (info.encoding or "utf-8").lower() not in _ENCODINGS or info.xml_version != "1.0":
                invalid[part] = (
                    f"XML {info.xml_version} in {info.encoding}, not 1.0 in UTF-8 or UTF-16",
                )
                continue
            try:
                form = canonical(root)
            except etree.LxmlError as exc:
                invalid[part] = (f"{type(exc).__name__}: {exc}",)
                continue
            digests[part] = hashlib.sha256(f"{ctype}\n".encode() + form).hexdigest()
            name = etree.QName(root).text
            expected = EXPECTED_ROOT.get(ctype)
            sheltered = name in _OWNED_ROOTS or (name in roots and ctype not in _GENERIC_XML)
            if expected is not None and name != expected:
                invalid[part] = (f"root {name} where {ctype} expects {expected}",)
            elif expected is None and sheltered:
                invalid[part] = (f"root {name} under {ctype}, a type that does not own it",)
            elif name not in roots:
                unchecked[part] = name
            else:
                try:
                    errors = validate(root, xsd)
                except etree.LxmlError as exc:
                    errors = [f"{type(exc).__name__}: {exc}"]
                namespaces, tags = unjudged(root)
                if namespaces:
                    over[part] = tuple(sorted(namespaces))
                if tags:
                    unreached[part] = tuple(sorted(tags))
                if errors:
                    invalid[part] = tuple(errors)
                else:
                    valid.append(part)
    return DeckReport(tuple(valid), invalid, unchecked, over, unreached, digests)


def replace_part(
    deck: pathlib.Path, part: str, data: bytes | None, out: pathlib.Path
) -> pathlib.Path:
    """A copy of ``deck`` at ``out`` with ``part`` holding ``data``: added where the deck has
    no such part, dropped where ``data`` is ``None``."""
    buf = io.BytesIO()
    with zipfile.ZipFile(deck) as src, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename != part:
                dst.writestr(info, src.read(info.filename))
            elif data is not None:
                dst.writestr(info, data)
        if part not in src.namelist() and data is not None:
            dst.writestr(part, data)
    out.write_bytes(buf.getvalue())
    return out
