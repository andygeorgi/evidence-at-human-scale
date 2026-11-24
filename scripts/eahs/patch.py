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
    return node[int(token)] if isinstance(node, list) else node[token]


def apply_ops(document, ops: List[dict]):
    """Return a deep copy of `document` with each op applied in order. Raises ValueError for a path that is not a pointer, KeyError/IndexError for one that leads nowhere."""
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
                parent[int(last)] = copy.deepcopy(op["value"])
            else:
                parent[last] = copy.deepcopy(op["value"])
        elif kind == "add":
            if isinstance(parent, list):
                if last == "-":
                    parent.append(copy.deepcopy(op["value"]))
                else:
                    parent.insert(int(last), copy.deepcopy(op["value"]))
            else:
                parent[last] = copy.deepcopy(op["value"])
        elif kind == "remove":
            if isinstance(parent, list):
                del parent[int(last)]
            else:
                del parent[last]
        else:
            raise ValueError("unknown op %r" % kind)
    return out
