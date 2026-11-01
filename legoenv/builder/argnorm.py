"""argnorm.py: the same argument normalisation the MCP smoke wrapper applies before env.call (json-string coercion by input_schema,
JMAP Foo/set {create:{...}} flattening), so replays / emitted witnesses use canonical args that plain runtime.Env accepts."""
import json
def normalize(spec, tool_name, args):
    t = next((x for x in spec["tools"] if x["tool"] == tool_name), None) or {}
    ins = t.get("input_schema") or {}
    if not isinstance(args, dict): return args
    fixed = dict(args)
    for k, v in args.items():
        pdef = ins.get(k); ptype = pdef.get("type") if isinstance(pdef, dict) else pdef
        if ptype == "json" and isinstance(v, str):
            try: fixed[k] = json.loads(v)
            except Exception: pass
    cr = fixed.get("create")
    if isinstance(cr, dict) and cr:
        inner = next(iter(cr.values())) if all(isinstance(v, dict) for v in cr.values()) else cr
        for k, v in inner.items():
            if k not in fixed or fixed[k] in (None, "", [], {}): fixed[k] = v
        fixed.pop("create", None)
    return fixed
def normalize_steps(spec, steps):
    return [dict(s, args=normalize(spec, s["tool"], s.get("args") or {})) for s in steps]
