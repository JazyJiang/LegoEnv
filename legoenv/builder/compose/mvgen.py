"""Deterministic namespace composition extracted without business changes.
Unused model clients, provider configuration and legacy generators are excluded.
"""
import copy, re
ENTITY_KEYS = {"entity", "child_entity", "snapshot_target",
               "account_entity", "account_link_entity"}
def slug(env_id):
    return re.sub(r"[^a-z0-9]+", "_", str(env_id).lower()).strip("_")

def _prefix_fk(v, pfx, ents):
    if isinstance(v, str) and "." in v:
        e, c = v.split(".", 1)
        if e in ents:
            return f"{pfx}__{e}.{c}"
    return v

def _walk(obj, pfx, ents):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "fk_to":
                out[k] = _prefix_fk(v, pfx, ents)
            elif k in ENTITY_KEYS and isinstance(v, str) and v in ents:
                out[k] = f"{pfx}__{v}"
            else:
                out[k] = _walk(v, pfx, ents)
        return out
    if isinstance(obj, list):
        return [_walk(x, pfx, ents) for x in obj]
    return obj

def namespace(spec, pfx):
    ents = {e["name"] for e in spec["entities"]}
    new_entities = []
    for e in spec["entities"]:
        e2 = _walk(e, pfx, ents)
        e2["name"] = f"{pfx}__{e['name']}"
        new_entities.append(e2)
    new_tools = []
    for t in spec["tools"]:
        t2 = _walk(t, pfx, ents)
        t2["tool"] = f"{pfx}__{t['tool']}"
        new_tools.append(t2)
    return {
        "env_id": spec.get("env_id"),
        "domain": spec.get("domain") or spec.get("about") or spec.get("description") or "",
        "entities": new_entities,
        "tools": new_tools,
        "auth": _walk(spec.get("auth", {}) or {}, pfx, ents),
        "seed_state": {f"{pfx}__{k}": copy.deepcopy(v) for k, v in spec.get("seed_state", {}).items()},
        "seed_sources": {f"{pfx}__{k}": _walk(v, pfx, ents) for k, v in spec.get("seed_sources", {}).items()},
        "joint_sources": {f"{pfx}__{g}": _walk(v, pfx, ents) for g, v in spec.get("joint_sources", {}).items()},
    }
