"""YAML numbers that remember how they were written.

YAML 1.1 reads ``1.10`` as ``1.1``. A spec's decimal numbers are loaded as ``int``/``float``
subclasses that keep their source text: arithmetic sees the number, ``str()`` gives back
what the author typed, and ``yaml.safe_dump`` writes that text back out.

A scalar YAML 1.1 reads as some other number than the decimal it shows — ``010`` as 8,
``0x1F`` as 31, ``16:9`` as 969 — loads as the text itself, so no field can print one
value and compute with another.
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


class SpecLoader(yaml.SafeLoader):
    """``SafeLoader``, with every number carrying its source text."""


def _int(loader: SpecLoader, node: yaml.ScalarNode) -> SourceInt | str:
    if _NOT_DECIMAL.fullmatch(node.value):
        return str(node.value)
    return SourceInt(loader.construct_yaml_int(node), node.value)


def _float(loader: SpecLoader, node: yaml.ScalarNode) -> SourceFloat | str:
    if _NOT_DECIMAL.fullmatch(node.value):
        return str(node.value)
    return SourceFloat(loader.construct_yaml_float(node), node.value)


SpecLoader.add_constructor("tag:yaml.org,2002:int", _int)
SpecLoader.add_constructor("tag:yaml.org,2002:float", _float)


def _represent(dumper: yaml.SafeDumper, data: SourceInt | SourceFloat) -> yaml.ScalarNode:
    tag = "tag:yaml.org,2002:int" if isinstance(data, int) else "tag:yaml.org,2002:float"
    return dumper.represent_scalar(tag, data.source)


yaml.SafeDumper.add_representer(SourceInt, _represent)
yaml.SafeDumper.add_representer(SourceFloat, _represent)
