"""A small JSON-Pointer patch (replace, remove, add) used to build counterfactuals and mutated copies in memory."""
from __future__ import annotations

import copy
import re
from typing import List

_BAD_ESCAPE = re.compile(r"~(?![01])")


def pointer_problem(pointer) -> str:
    """Why a value is not a JSON pointer (RFC 6901) to a place below the document root that this patch can follow, or "" if it is one.

    A pointer starts with "/" and has a name in every step. A path written without the leading "/" is not a pointer: it used to be read
    as one, so that a counterfactual or a mutation with a slip in its path was replayed all the same.
    """
    if not isinstance(pointer, str):
        return "it is not text"
    if not pointer.startswith("/") or pointer == "/":
        return "it must start with '/' and name a place below the root, for example /limits_lifecycle/expiry"
    if "//" in pointer or pointer.endswith("/"):
        return "it has an empty step"
    if _BAD_ESCAPE.search(pointer):
        return "inside a name, '~' must be written ~0 and '/' must be written ~1"
    return ""


def _tokens(pointer: str) -> List[str]:
    problem = pointer_problem(pointer)
    if problem:
        raise ValueError("%r is not a JSON pointer: %s" % (pointer, problem))
    return [t.replace("~1", "/").replace("~0", "~") for t in pointer[1:].split("/")]


def _step(node, token):
    """One step down: a name in an object, or a position in a list. A position is written as 0 or as digits without a leading zero, and must exist."""
    if isinstance(node, list):
        return node[_position(token, len(node))]
    return node[token]


def _position(token: str, length: int, appending: bool = False) -> int:
    """The position a pointer step names in a list of `length` items, or an error. `-` and a position past the end are not positions that exist
    (the end, for an add, is `length` or `-`: the caller decides). int() would also read " 1", "+1", "1_0" and "-1" (the last item), and a huge number
    would end in an overflow, so the step is read by its digits only."""
    if not re.fullmatch(r"0|[1-9][0-9]*", token):
        raise ValueError("%r is not a position in a list: write 0, 1, 2 and so on, without a sign, a space or a leading zero" % token)
    position = int(token)
    if position > length or (position == length and not appending):
        raise IndexError("the list has %d item%s, so there is no position %s" % (length, "" if length == 1 else "s", token))
    return position


def apply_ops(document, ops: List[dict]):
    """Return a deep copy of `document` with each op applied in order. Raises ValueError for a path that is not a pointer or a step that is not a
    position, KeyError/IndexError for one that leads nowhere (an add may name the end of a list: its length, or `-`)."""
    out = copy.deepcopy(document)
    for op in ops:
        tokens = _tokens(op["path"])
        parent = out
        for token in tokens[:-1]:
            parent = _step(parent, token)
        last = tokens[-1]
        kind = op["op"]
        if kind == "replace":
            _step(parent, last)  # the target must already exist
            if isinstance(parent, list):
                parent[_position(last, len(parent))] = copy.deepcopy(op["value"])
            else:
                parent[last] = copy.deepcopy(op["value"])
        elif kind == "add":
            if isinstance(parent, list):
                if last == "-":
                    parent.append(copy.deepcopy(op["value"]))
                else:
                    parent.insert(_position(last, len(parent), appending=True), copy.deepcopy(op["value"]))
            else:
                parent[last] = copy.deepcopy(op["value"])
        elif kind == "remove":
            if isinstance(parent, list):
                del parent[_position(last, len(parent))]
            else:
                del parent[last]
        else:
            raise ValueError("unknown op %r" % kind)
    return out
