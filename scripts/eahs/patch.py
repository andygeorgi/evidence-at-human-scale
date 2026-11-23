"""A small JSON-Pointer patch (replace, remove, add) used to build counterfactuals and mutated copies in memory."""
from __future__ import annotations

import copy
from typing import List


def _tokens(pointer: str) -> List[str]:
    return [t.replace("~1", "/").replace("~0", "~") for t in pointer.lstrip("/").split("/")] if pointer.strip("/") else []


def _step(node, token):
    return node[int(token)] if isinstance(node, list) else node[token]


def apply_ops(document, ops: List[dict]):
    """Return a deep copy of `document` with each op applied in order. Raises KeyError/IndexError for a bad path."""
    out = copy.deepcopy(document)
    for op in ops:
        tokens = _tokens(op["path"])
        if not tokens:
            raise KeyError("an op needs a path below the document root")
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
