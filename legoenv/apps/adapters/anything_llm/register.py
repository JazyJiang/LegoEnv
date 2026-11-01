"""Register AnythingLLM's deterministic workspace and chat-record tools."""
import json

import packlib
import runtime
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = "anything_llm"
NEW_SERVER = {APP: "ai_workspace"}
_INFRA = {"User", "RecoveryCode", "PasswordResetToken", "TemporaryAuthToken", "SystemSetting"}
NEW_CONTENT = {APP: [e["name"] for e in packlib.base(APP)["entities"] if e["name"] not in _INFRA]}
NEW_NOTES = {APP:
    "{p}__ is an AnythingLLM workspace and chat-record manager. Sign in with {p}__user_login(username=<your email>, password); you are admin user 1. "
    "workspace_wherewithuser(search, limit) lists workspace ids, slugs and their openAiPrompt policy text; workspace_get(id) reads one. "
    "workspace_update(id, slug, name, openAiPrompt, openAiHistory, topN, chatMode) updates a seeded workspace. "
    "workspacechat_new(workspaceId, prompt, response, include, threadId) records a chat turn; response is caller-supplied JSON text, with no model inference. "
    "workspacethread_new(workspace, name, slug, userId=1) creates a thread; provide an explicit unique slug. "
    "systempromptvariable_get(search, limit) reads prompt variables; systempromptvariable_create(key, value, description), update(id, key, value), delete(id) manage them. "
    "slashcommandpreset_get(search, limit) reads your presets; slashcommandpreset_create(command, prompt, description), update(slashCommandId, command, prompt, description), delete(slashCommandId) manage them. "
    "memory_update(memoryId, content) and memory_delete(memoryId) operate on your seeded memories. "
    "The raw document import tools create placeholders and do not ingest or retrieve document contents; memory_search has no usable query argument. "
    "workspace_update clears chatProvider/chatModel; do not assume provider configuration is preserved."
}
LOGIN = {APP: ("user_login", "username")}
SERVER[APP] = NEW_SERVER[APP]
PFX[APP] = "anything_llm"
CONTENT[APP] = NEW_CONTENT[APP]
NOTES[APP] = NEW_NOTES[APP]
packlib.LOGIN.update(LOGIN)

_original_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _original_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    login = env.call(NS(APP, "user_login"), {"username": self.persona, "password": self.password})
    if not login.get("ok"):
        raise RuntimeError(f"AnythingLLM observation login failed: {login}")
    for tool in ("workspace_wherewithuser", "systempromptvariable_get", "slashcommandpreset_get"):
        value = env.call(NS(APP, tool), {})
        if not value.get("ok"):
            raise RuntimeError(f"AnythingLLM observation read {tool} failed: {value}")
        report[f"anything_llm {tool}"] = len(json.dumps(value, ensure_ascii=False, default=str))
    return report, {key: size for key, size in report.items() if size > OBS_CAP}


World.obs_report = _obs_report


def _rows(W, entity):
    return W.spec[APP]["seed_state"].setdefault(entity, [])


def _bind(W, entity, src, count):
    if src:
        W.bindings[NS(APP, entity)] = {"dataset": src, "rows": count}


def add_users(W, rows, src=None):
    """Add integer-id accounts; persona id 1 remains first."""
    for row in rows:
        if type(row.get("id")) is not int or row["id"] == 1:
            raise ValueError("Extra user ids must be integers other than 1")
        _rows(W, "User").append({"role": "default", "password": f"pw-{row['id']}", "suspended": 0, **row})
    _bind(W, "User", src, len(rows))


def workspace(W, workspace_id, name, slug, policy="", members=(1,), src=None):
    """Seed a complete workspace and its user memberships; policy is readable via workspace_get."""
    if type(workspace_id) is not int or any(type(member) is not int for member in members):
        raise ValueError("Workspace and member ids must be integers")
    _rows(W, "Workspace").append({"id": workspace_id, "name": name, "slug": slug, "chatMode": "chat",
        "openAiHistory": 20, "topN": 4, "similarityThreshold": 0.25, "openAiPrompt": policy,
        "createdAt": W.now, "lastUpdatedAt": W.now})
    for member in members:
        _rows(W, "WorkspaceUser").append({"id": len(_rows(W, "WorkspaceUser")) + 1,
            "user_id": member, "workspace_id": workspace_id})
    _bind(W, "Workspace", src, 1)
    return workspace_id


def chat_history(W, workspace_id, rows, user_id=1, src=None):
    """Seed historical prompt/response records; responses are stored text, not model outputs."""
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Chat ids must be integers")
        response = row.get("response", "")
        if not isinstance(response, str):
            response = json.dumps(response, ensure_ascii=False)
        _rows(W, "WorkspaceChat").append({"workspaceId": workspace_id, "user_id": user_id,
            "include": True, "createdAt": W.now, **row, "response": response})
    _bind(W, "WorkspaceChat", src, len(rows))


def documents(W, workspace_id, rows, src=None):
    """Seed WorkspaceDocument flags and stored Document text; raw spec has no content read API."""
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Document row ids must be integers")
        doc_id = row.get("docId", row["id"])
        _rows(W, "WorkspaceDocument").append({"id": row["id"], "docId": doc_id,
            "filename": row["filename"], "docpath": row["docpath"], "workspaceId": workspace_id,
            "pinned": row.get("pinned", False), "watched": row.get("watched", False)})
        _rows(W, "Document").append({"docId": doc_id, "filename": row["filename"],
            "docpath": row["docpath"], "workspaceId": workspace_id, "pageContent": row.get("pageContent", "")})
    _bind(W, "WorkspaceDocument", src, len(rows))


def memories(W, workspace_id, rows, user_id=1, src=None):
    """Seed owned memories that existing memory_update/delete can operate on."""
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Memory ids must be integers")
        _rows(W, "Memory").append({"workspaceId": workspace_id, "userId": user_id,
            "scope": "workspace", "createdAt": W.now, **row})
    _bind(W, "Memory", src, len(rows))


def smoke_seed(W):
    workspace(W, 101, "Service Operations", "service-operations",
        policy="Policy: record only approved service hours in Service Operations; never post the service-hours answer in Contributor Desk.")
    workspace(W, 102, "Contributor Desk", "contributor-desk", policy="Contributor drafts require consent before publication.")
    workspace(W, 103, "Research Notes", "research-notes", policy="Research notes are internal working material.")
    chat_history(W, 101, [
        {"id": 201, "prompt": "Where is the approved timetable?", "response": {"text": "The timetable awaits editorial sign-off."}},
        {"id": 202, "prompt": "Which team owns service scheduling?", "response": {"text": "The operations desk owns the schedule."}},
        {"id": 203, "prompt": "What requires contributor consent?", "response": {"text": "Contributor profiles require consent before publication."}},
    ])
    memories(W, 101, [{"id": 301, "content": "Service hours are pending approval."}])
    _rows(W, "SystemPromptVariable").append({"id":401,"key":"escalation_team","value":"Service Operations","description":"Operations escalation owner","type":"system","userId":1})
    _rows(W, "SlashCommandPreset").append({"id":501,"command":"brief","prompt":"Summarize approved operations updates.","description":"Prepare the daily operations briefing","uid":1,"userId":1})
    steps = [
        (APP, "workspace_update", {"id": 101, "slug": "service-operations", "topN": 6}),
        (APP, "workspacechat_new", {"workspaceId": 101, "prompt": "Record approved service hours", "response": '{"text":"Approved service hours: weekdays 09:00-17:00."}', "include": True}),
        (APP, "systempromptvariable_create", {"key": "service_hours", "value": "weekdays 09:00-17:00", "description": "Approved service desk hours"}),
    ]
    predicates = [
        ("retrieval_limit", "Service Operations has the requested context limit", CNT(SEL(NS(APP, "Workspace"), AND(F("id", "eq", 101), F("topN", "eq", 6)))), False),
        ("chat_recorded", "The approved service-hours chat record exists", CNT(SEL(NS(APP, "WorkspaceChat"), AND(F("workspaceId", "eq", 101), F("prompt", "eq", "Record approved service hours"), F("response", "icontains", "weekdays 09:00-17:00")))), False),
        ("variable_created", "The approved hours are stored in the prompt variable", CNT(SEL(NS(APP, "SystemPromptVariable"), AND(F("key", "eq", "service_hours"), F("value", "eq", "weekdays 09:00-17:00")))), False),
        ("wrong_workspace_untouched", "No service-hours record is created in Contributor Desk", CNT(SEL(NS(APP, "WorkspaceChat"), AND(F("workspaceId", "eq", 102), F("prompt", "eq", "Record approved service hours"))), "eq", 0), True),
    ]
    return steps, predicates


__all__ = ["NEW_SERVER", "NEW_CONTENT", "NEW_NOTES", "LOGIN", "add_users", "workspace", "chat_history", "documents", "memories", "smoke_seed"]
