"""Lossless JSON form of one BILLSTATUS XML file, and the checks that prove it is lossless.

``parse_billstatus_xml`` reads the fields the typed tables model. The record built here keeps
*everything* the source says, so a field nobody has modelled yet is still stored, queryable
(``record -> 'bill' -> 'summaries'``) and re-derivable, instead of being dropped at load.

Encoding (an element becomes a value):

- no children, no attributes: its text, stripped of layout whitespace, else ``""``
- otherwise an object: children by tag, ``@name`` for an attribute, ``#text`` for text that
  sits beside children
- a tag that repeats within its parent, or is one of ``LIST_TAGS``, is always an array (so a
  bill with one action has the same shape as one with fifty)
- namespaced tags use a prefix (``dc:rights``); unknown namespaces keep ``{uri}name``

Text after a child element (a tail) has nowhere to go; it raises rather than being lost.

``xml_paths`` / ``record_paths`` and ``xml_leaves`` / ``record_leaves`` are the two sides of the
losslessness check: the same element paths, and the same (path, value) leaves, before and after.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any
from xml.etree import ElementTree

# Tags whose parent may hold one or many: always arrays, so query shapes do not depend on the count.
LIST_TAGS = frozenset(
    {"item", "summary", "committeeReport", "link", "recordedVote", "amendment"}
)
NAMESPACE_PREFIXES = {"http://purl.org/dc/elements/1.1/": "dc"}


def _name(tag: str) -> str:
    """``{uri}local`` -> ``prefix:local`` for known namespaces, unchanged otherwise."""
    if tag.startswith("{"):
        uri, _, local = tag[1:].partition("}")
        prefix = NAMESPACE_PREFIXES.get(uri)
        return f"{prefix}:{local}" if prefix else tag
    return tag


def _text(element: ElementTree.Element) -> str:
    return (element.text or "").strip()


def _check_no_tail(child: ElementTree.Element, parent_path: str) -> None:
    if (child.tail or "").strip():
        raise ValueError(
            f"text after <{_name(child.tag)}> in {parent_path} (a tail) cannot be recorded"
        )


def _value(element: ElementTree.Element, path: str, list_tags: frozenset[str]) -> Any:
    children = list(element)
    if not children and not element.attrib:
        return _text(element)
    value: dict[str, Any] = {f"@{_name(k)}": v for k, v in element.attrib.items()}
    if text := _text(element):
        value["#text"] = text
    groups: dict[str, list[Any]] = {}
    for child in children:
        _check_no_tail(child, path)
        name = _name(child.tag)
        groups.setdefault(name, []).append(_value(child, f"{path}/{name}", list_tags))
    for name, values in groups.items():
        value[name] = values if len(values) > 1 or name in list_tags else values[0]
    return value


def xml_to_record(
    root: ElementTree.Element, list_tags: frozenset[str] = LIST_TAGS
) -> dict[str, Any]:
    """The lossless JSON form of ``root``'s content (the root tag itself is not a key).

    ``list_tags`` names the tags that are always arrays; BILLSTATUS's are the default, another
    source (the House Clerk's roll calls) passes its own.
    """
    value = _value(root, f"/{_name(root.tag)}", list_tags)
    return value if isinstance(value, dict) else {"#text": value}


def record_sha256(record: dict[str, Any]) -> str:
    """Digest of the record's canonical JSON, to tell a changed bill from an unchanged one."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# -- the XML side of the check --------------------------------------------------------
def xml_paths(root: ElementTree.Element) -> set[str]:
    """Every element and attribute path in the tree (``/billStatus/bill/title``)."""
    paths: set[str] = set()

    def walk(element: ElementTree.Element, prefix: str) -> None:
        path = f"{prefix}/{_name(element.tag)}"
        paths.add(path)
        for name in element.attrib:
            paths.add(f"{path}/@{_name(name)}")
        for child in element:
            walk(child, path)

    walk(root, "")
    return paths


def xml_leaves(root: ElementTree.Element) -> Counter[tuple[str, str]]:
    """Every (path, text) pair: leaf text, attribute values, and text beside children."""
    leaves: Counter[tuple[str, str]] = Counter()

    def walk(element: ElementTree.Element, prefix: str) -> None:
        path = f"{prefix}/{_name(element.tag)}"
        for name, value in element.attrib.items():
            leaves[(f"{path}/@{_name(name)}", value)] += 1
        text = _text(element)
        if not len(element) and not element.attrib:
            leaves[(path, text)] += 1
        elif text:
            leaves[(f"{path}/#text", text)] += 1
        for child in element:
            walk(child, path)

    walk(root, "")
    return leaves


# -- the record side of the check ----------------------------------------------------
def _members(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def record_paths(record: dict[str, Any], root_tag: str) -> set[str]:
    """Every element and attribute path the record holds, spelled like ``xml_paths``."""
    paths: set[str] = set()

    def walk(value: Any, path: str) -> None:
        paths.add(path)
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            if key == "#text":
                continue
            if key.startswith("@"):
                paths.add(f"{path}/{key}")
                continue
            for member in _members(child):
                walk(member, f"{path}/{key}")

    walk(record, f"/{_name(root_tag)}")
    return paths


def record_leaves(record: dict[str, Any], root_tag: str) -> Counter[tuple[str, str]]:
    """Every (path, text) pair the record holds, spelled like ``xml_leaves``."""
    leaves: Counter[tuple[str, str]] = Counter()

    def walk(value: Any, path: str) -> None:
        if not isinstance(value, dict):
            leaves[(path, value)] += 1
            return
        for key, child in value.items():
            if key == "#text" or key.startswith("@"):
                leaves[(f"{path}/{key}", child)] += 1
                continue
            for member in _members(child):
                walk(member, f"{path}/{key}")

    walk(record, f"/{_name(root_tag)}")
    return leaves


def record_problems(root: ElementTree.Element, record: dict[str, Any]) -> list[str]:
    """What the record lost or invented relative to ``root``; empty means lossless."""
    problems: list[str] = []
    want_paths, have_paths = xml_paths(root), record_paths(record, root.tag)
    problems += [f"path not captured: {p}" for p in sorted(want_paths - have_paths)]
    problems += [f"path invented: {p}" for p in sorted(have_paths - want_paths)]
    want, have = xml_leaves(root), record_leaves(record, root.tag)
    for key in sorted(set(want) | set(have)):
        if want[key] != have[key]:
            problems.append(f"value differs at {key[0]}: xml has {want[key]}x, record {have[key]}x")
    return problems
