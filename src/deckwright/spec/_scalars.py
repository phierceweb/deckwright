"""YAML scalars that remember how they were written.

YAML 1.1 reads ``1.10`` as ``1.1``. A spec's decimal numbers are loaded as ``int``/``float``
subclasses that keep their source text: arithmetic sees the number, ``str()`` gives back
what the author typed, and ``yaml.safe_dump`` writes that text back out.

A scalar YAML 1.1 reads as some other number than the decimal it shows — ``010`` as 8,
``0x1F`` as 31, ``16:9`` as 969 — loads as the text itself, so no field can print one
value and compute with another.

``true`` and ``false`` load as bools. The other YAML 1.1 booleans — ``yes``, ``no``, ``on``,
``off`` — load as :class:`BoolWord`, text that prints as written: a field taking true or
false reads it through :func:`boolean`, and optional copy checks it with :func:`has_text`.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

_NOT_DECIMAL = re.compile(r"[-+]?(?:0[0-7_]+|0[bx].*|.*:.*)")


class SourceInt(int):
    source: str

    def __new__(cls, value: int, source: str) -> SourceInt:
        obj = super().__new__(cls, value)
        obj.source = source
        return obj

    def __str__(self) -> str:
        return self.source

    def __reduce__(self) -> tuple[Any, ...]:
        return (SourceInt, (int(self), self.source))


class SourceFloat(float):
    source: str

    def __new__(cls, value: float, source: str) -> SourceFloat:
        obj = super().__new__(cls, value)
        obj.source = source
        return obj

    def __str__(self) -> str:
        return self.source

    def __reduce__(self) -> tuple[Any, ...]:
        return (SourceFloat, (float(self), self.source))


class BoolWord(str):
    """``yes``, ``no``, ``on`` or ``off`` as written; ``bool()`` is the truth YAML 1.1 reads."""

    truth: bool

    def __new__(cls, source: str, truth: bool) -> BoolWord:
        obj = super().__new__(cls, source)
        obj.truth = truth
        return obj

    def __bool__(self) -> bool:
        return self.truth

    def __reduce__(self) -> tuple[Any, ...]:
        return (BoolWord, (str(self), self.truth))


def boolean(value: Any) -> Any:
    """A true-or-false field's value, with a :class:`BoolWord` read as the bool it spells.

    Anything else passes through unchanged, for the field's own check to accept or refuse.
    """
    return value.truth if isinstance(value, BoolWord) else value


def has_text(value: Any) -> bool:
    """Whether an optional copy field holds anything to set: ``no`` and ``off`` are words."""
    return isinstance(value, BoolWord) or bool(value)


class SpecLoader(yaml.SafeLoader):
    """``SafeLoader``, with every number and boolean word carrying its source text."""


def _int(loader: SpecLoader, node: yaml.ScalarNode) -> SourceInt | str:
    if _NOT_DECIMAL.fullmatch(node.value):
        return str(node.value)
    return SourceInt(loader.construct_yaml_int(node), node.value)


def _float(loader: SpecLoader, node: yaml.ScalarNode) -> SourceFloat | str:
    if _NOT_DECIMAL.fullmatch(node.value):
        return str(node.value)
    return SourceFloat(loader.construct_yaml_float(node), node.value)


def _bool(loader: SpecLoader, node: yaml.ScalarNode) -> bool | BoolWord:
    word = str(loader.construct_scalar(node))
    truth = loader.bool_values.get(word.lower())
    if truth is None:
        raise yaml.constructor.ConstructorError(
            None, None, f"{word!r} is not a boolean", node.start_mark
        )
    return truth if word.lower() in ("true", "false") else BoolWord(word, truth)


SpecLoader.add_constructor("tag:yaml.org,2002:int", _int)
SpecLoader.add_constructor("tag:yaml.org,2002:float", _float)
SpecLoader.add_constructor("tag:yaml.org,2002:bool", _bool)


def _represent(dumper: yaml.SafeDumper, data: SourceInt | SourceFloat) -> yaml.ScalarNode:
    tag = "tag:yaml.org,2002:int" if isinstance(data, int) else "tag:yaml.org,2002:float"
    return dumper.represent_scalar(tag, data.source)


def _represent_word(dumper: yaml.SafeDumper, data: BoolWord) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:bool", str(data))


yaml.SafeDumper.add_representer(SourceInt, _represent)
yaml.SafeDumper.add_representer(SourceFloat, _represent)
yaml.SafeDumper.add_representer(BoolWord, _represent_word)
