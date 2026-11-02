"""A key YAML resolved into something other than text is refused by name, never by a TypeError."""

from __future__ import annotations

from datetime import date

import pytest

from deckwright.errors import SpecError
from deckwright.utils.keys import refuse_unknown, unknown_field

KNOWN = ("theme", "title")


@pytest.mark.parametrize(
    ("key", "named", "read"),
    [
        (True, "unknown field true;", "an unquoted yes, on or true as the boolean true"),
        (False, "unknown field false;", "an unquoted no, off or false as the boolean false"),
        (None, "unknown field null;", "an empty key, ~ or null as null"),
        (date(2021, 1, 1), "unknown field 2021-01-01;", "2021-01-01 as a date"),
        (12, "unknown field 12;", "12 as a number"),
    ],
)
def test_a_key_yaml_resolved_is_named_as_yaml_read_it(key, named, read):
    message = unknown_field(key, KNOWN, suggest=True)
    assert named in message
    assert message.endswith(f" — YAML reads {read}; quote the key")


def test_keys_of_mixed_types_are_ordered_as_text():
    """`sorted` on a date beside a string raises TypeError; ordered as text, the date
    ('2021-01-01') comes before 'zzz' and is the one named."""
    with pytest.raises(SpecError, match=r"^unknown field 2021-01-01; known fields: theme, title"):
        refuse_unknown({date(2021, 1, 1): 1, "zzz": 2, "title": 3}, KNOWN, error=SpecError)
