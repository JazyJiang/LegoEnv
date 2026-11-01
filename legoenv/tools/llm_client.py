"""Minimal OpenAI-compatible chat client for the atom tools (atoms/data/tag_datasets.py, atoms/server/onboarding/screen_specs.py).

Uses legoenv/tools/openai_bridge.completion_url, the same endpoint rules as tools/collect.py:
POST <base>/chat/completions with an optional Bearer key read from the variable named by --api-key-env."""
import argparse, json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openai_bridge import completion_url


def add_endpoint_args(ap, required=True):
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"), required=required and not os.environ.get("OPENAI_BASE_URL"))
    ap.add_argument("--model", default=os.environ.get("OPENAI_MODEL"), required=required and not os.environ.get("OPENAI_MODEL"))
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY", help="name of the variable that holds the key")
    ap.add_argument("--extra-body", default="{}", help="optional provider-specific JSON fields")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--request-timeout", type=float, default=600)
    return ap


def chat(a, content):
    body = {"model": a.model, "messages": [{"role": "user", "content": content}], "temperature": 0,
            "max_tokens": a.max_tokens, "stream": False, **json.loads(a.extra_body)}
    headers = {"Content-Type": "application/json"}
    key = os.environ.get(a.api_key_env)
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(completion_url(a.base_url), data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=a.request_timeout) as r:
        return json.load(r)["choices"][0]["message"].get("content") or ""
