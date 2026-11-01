#!/usr/bin/env python3
"""Build Spec node: prep (det) -> agent -> probe (det) -> feedback round -> cache.

Runs once per repo; the product is cached permanently and reused by every downstream
task. The rule of the whole pipeline is "run it for real before claiming it", and the
spec is no exception — this is the op-first principle applied to its own first stage.

  ① prep      collect -> spec.raw.json (full candidate set) + per-layer drop accounting. **Zero LLM.**
  ② agent     reads raw + collect + build_report -> writes spec.draft.json. **Judgement only.**
  ③ probe     L0 structure / L1 builds / L2 actually drives / L3 hits walls. **Zero LLM.**
  ④ feedback  probe results are appended to the agent's **own session** (resume), <= R_BUILD rounds.
              **det finds the faults, whoever wrote the spec fixes them** — det only supplies
              evidence; it does not decide how to fix.
  ⑤ gate      L1 passes + login works + >=1 write tool wrote + >=1 read tool returned.

⚠ The probe uses a throwaway seed synthesized by `build_seed`, **kept in memory only**.
  The `seed_state` in the written spec is **the agent's own smoke seed** and has nothing
  to do with the probe data — see the three-layer seed notes at the top of build_seed.
"""
import os, sys, json, time, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import _rt  # noqa: E402,F401  (puts the runtime directory on sys.path)

import build_prep as PREP  # noqa: E402
import build_probe as PROBE  # noqa: E402
import cc_driver as CC  # noqa: E402

_PROMPTS = os.path.join(_HERE, "..", "..", "prompts")
PROMPT = os.path.join(_PROMPTS, "build_spec.md")
FEEDBACK = os.path.join(_PROMPTS, "build_spec_feedback.md")
# Output directory for specs that pass the gate (the base_specs format).
# Set by the CLI (--spec-dir) or by callers via ``set_spec_dir``.
REPO_SPEC_CACHE = os.environ.get("LEGOENV_SPEC_DIR", "repo_specs")


def set_spec_dir(path):
    global REPO_SPEC_CACHE
    REPO_SPEC_CACHE = path


# **Only one feedback round.** More rounds push the agent toward "making the findings go
# away" — deleting real guards, changing correct declarations, just so the report looks
# clean. The thing this pipeline fears most is "passing for the wrong reason". One round =
# one chance to respond, minimal pressure; whatever remains goes into `residual` as an
# honest account instead of pretending it was solved.
R_BUILD = int(os.environ.get("LEGOENV_R_BUILD", "1"))


def _fill(tpl, **kw):
    for k, v in kw.items():
        tpl = tpl.replace("__%s__" % k, v)
    return tpl


def base_labels(base_rep, base_spec):
    """Problem labels for each `id_local` on the candidate spec — used to flag **regressions**
    in the feedback.

    **Aligned by id_local, not by tool name**: renaming is the agent's job (its second piece of
    judgement), so names are bound not to match. Only tools that still carry
    `_evidence.id_local` are covered — the agent sometimes deletes `_evidence` too; those cannot
    be matched, and not flagging beats flagging wrongly.
    """
    m = {t.get("tool"): (t.get("_evidence") or {}).get("id_local")
         for t in ((base_spec or {}).get("tools") or [])}
    # ⚠ `known` means "the probe **actually ran** it in the candidate round", not "the candidate
    #   spec contains this tool". If the candidate's L1 did not build, L2 is skipped entirely —
    #   that round tells us nothing about any tool.
    #   This used to ignore that, so when base_rep had no l2, reg was empty while known was full,
    #   and **every** tool with an id_local got flagged "<- [REGRESSION] it was fine in the candidate".
    #   A report where everything is flagged as a regression is equivalent to no flags, and more
    #   misleading.
    _ran = bool((base_rep or {}).get("l2"))
    known = {v for v in m.values() if v} if _ran else set()
    out = {}
    for k in ("no_op", "wrong_entity", "bad_exec_spec"):
        for tn in (((base_rep or {}).get("l2") or {}).get(k) or []):
            idl = m.get(tn)
            if idl:
                out.setdefault(k, set()).add(idl)
    return out, known


def _cut(items, n, what):
    """Truncation must be visible. **Silently listing fewer is lying that "that's all"** — the
    same discipline we hold det to applies to reports given to the agent: if it sees 40 items,
    it does not know there are 260 more."""
    items = list(items)
    if len(items) <= n:
        return items
    return items[:n] + ["… %d more %s not listed (%d in total)"
                        % (len(items) - n, what, len(items))]


def _brief(rep, spec=None, base=None, base_spec=None):
    """Probe results -> the sections shown to the agent. **Never paste sample rows** — the agent
    reads this, and given data it may copy the probe's junk rows into its own draft seed: that
    would be contamination leaking in through the report.

    `base` / `base_spec` are **the run on the candidate spec**. With them we can flag
    **regressions** — "this tool was fine before you changed it". That carries far more
    information than "this tool is broken", especially for `bad_exec_spec`: that class is almost
    always the agent collapsing a structured field det filled correctly into a scalar inside it.
    """
    reg, known = base_labels(base, base_spec) if base is not None else ({}, set())
    _idl = {t.get("tool"): (t.get("_evidence") or {}).get("id_local")
            for t in ((spec or {}).get("tools") or [])}

    def _mark(name, key):
        """**Regression = fine in the candidate, broken after the edit**, not "broken in the
        candidate too".

        All three conditions are required: the `id_local` matches (otherwise there is nothing to
        compare), that id_local **was run by the probe in the candidate** (`known`; otherwise "no
        record" and "no problem at the time" are indistinguishable), and it is **not** on the
        candidate round's problem list. Anything unmatched is left unflagged — a wrong flag is
        worse than none.
        """
        idl = _idl.get(name)
        return ("%s  ← [REGRESSION] it was fine in the candidate spec" % name
                if idl and idl in known and idl not in reg.get(key, ()) else name)

    l0 = rep.get("l0") or {}
    # err and warn used to be rendered in the same shape (`· [X] ...`) and sent together — the
    # agent could not tell what **must be fixed** from what is only a hint. Split them into two
    # sections, each with a heading and a count.
    e = _cut(["· [%s] %s" % (w, x) for w, x in (l0.get("err") or [])], 40, "L0 err")
    w = _cut(["· [%s] %s" % (a, b) for a, b in (l0.get("warn") or [])], 20, "L0 warn")
    _s0 = []
    if e: _s0 += ["ERR (%d) — these break the spec; fix them:" % l0.get("n_err", 0)] + e
    if w: _s0 += ["", "WARN (%d) — smells; use your judgement:" % l0.get("n_warn", 0)] + w
    s0 = "\n".join(_s0) if _s0 else "(clean — 0 err, 0 warn)"
    l1 = rep.get("l1") or {}
    s1 = "OK" if l1.get("ok") else "FAILED: %s" % l1.get("why")
    l2 = rep.get("l2") or {}
    if l2:
        _cnt = l2.get("counts") or {}
        # Login success goes at the very top. Buried in notes it might as well be unsaid: when
        # login fails, every tool below that needs auth is marked guarded, and in this report
        # guarded by default means "the wall is working" — so a report with a broken auth block
        # reads like a report where everything is fine, and the agent only gets this one round.
        _lg = l2.get("login") or {}
        if _lg.get("ok") is False:
            _head = ("!! LOGIN FAILED (%s): %s\n"
                     "   **Every `guarded` below is caused by this, not by a wall doing its job.**\n"
                     "   Fix `auth` (account_entity / username_col / password_col) and the login\n"
                     "   tool’s `exec_spec.verify` first — nothing else on this page can be\n"
                     "   trusted until the probe can sign in.\n" % (_lg.get("tool"), _lg.get("why")))
        elif _lg.get("ok") is None:
            _head = ("!! NOT LOGGED IN: %s. Everything below was driven anonymously.\n"
                     % _lg.get("why"))
        else:
            _head = ""

        def _lst(k):
            v = [_mark(x, k) for x in (l2.get(k) or [])]
            if not v:
                return ""
            # ⚠ The numerator must be **the number actually printed**; the denominator is the
            #   **full count** from counts. These lists were already cut once in build_probe
            #   ([:40] / [:20]), so using len(v) as the total means the promise "always annotate
            #   a truncated list" **never fires** — we promised it to the agent and never kept it.
            _tot = _cnt.get(k, len(v))
            body = "; ".join(v[:40])
            more = ("  (**%d shown of %d** — this is a sample, not the list)"
                    % (min(len(v), 40), _tot)) if _tot > min(len(v), 40) else ""
            return "%s: %s%s\n" % (k, body, more)
        s2 = (_head
              + "counts: %s\n" % json.dumps(l2.get("counts") or {}, ensure_ascii=False)
              + _lst("no_op") + _lst("wrong_entity") + _lst("bad_exec_spec")
              + "\n".join("· " + x for x in _cut(l2.get("notes") or [], 15, "note")))
    else:
        s2 = "(skipped — L1 did not build. **A skip is an account, not a pass.**)"
    l3 = rep.get("l3") or {}
    if l3:
        _p3 = ["counts: %s" % json.dumps(l3.get("counts") or {}, ensure_ascii=False),
               "  (keys read `<wall kind>/<verdict>`; the kinds and verdicts are explained above)"]
        _wm = ["· %s — declared a %s wall, the violation was NOT refused"
               % (a, b) for a, b in (l3.get("wall_missing") or [])]
        if _wm:
            _p3 += ["", "wall_missing (%d):" % l3.get("n_wall_missing", len(_wm))] + _cut(_wm, 40, "wall_missing")
        _pe = l3.get("probe_error") or []
        if _pe:
            # probe_error has the same origin as bad_exec_spec: the probe crashed walking the
            # exec_spec the way the runtime does. It is **not** a probe limitation, so it must
            # never be mixed into the same section as unverifiable.
            _p3 += ["", "probe_error (%d) — the probe crashed walking this tool. Same family as"
                        % l3.get("n_probe_error", len(_pe)),
                    "`bad_exec_spec`: the runtime walks it the same way and will crash too. **A defect, not a limit.**"]
            _p3 += ["· %s — %s" % (a, wy) for a, wy in _pe[:20]]
        _uw = l3.get("unverifiable_why") or {}
        if _uw:
            _p3 += ["", "unverifiable (%d) — the probe could not build the violating scenario."
                        % l3.get("n_unverifiable", 0),
                    "**The reason matters**: \"no duplicable row in the seed\" is the probe’s limit,",
                    "while an exception name is usually a shape you wrote."]
            for k, v in sorted(_uw.items()):
                _p3 += ["  %s:" % k] + ["    · " + x for x in v]
        s3 = "\n".join(_p3)
    else:
        s3 = "(skipped — L1 did not build. **A skip is an account, not a pass.**)"
    cov = "tools %d · entities %d" % (rep.get("tools", 0), rep.get("entities", 0))
    ne = (rep.get("l0") or {}).get("n_no_evidence", 0)
    if ne:
        cov += ("\n%d guards carry no `_evidence.edges`. The contract is explicit: a wall you "
                "cannot evidence must not be written. Either restore the evidence the pre-pass "
                "gave you, or delete the wall." % ne)
    if spec is not None:
        fam = {}
        for t in (spec.get("tools") or []):
            fam[t.get("family")] = fam.get(t.get("family"), 0) + 1
        cov += "\nfamilies: %s" % json.dumps(fam, ensure_ascii=False)

    # seal accounting: **every in-place rewrite** det made to the spec before the probe.
    # It was always computed and written to build_report, but never shown to the agent — and
    # among them "spec has no auth.account_entity, N $actor.<col> have nowhere to resolve" is the
    # most critical: it means **none** of the tenant-boundary guards in the spec take effect,
    # while the report only shows a pile of normal-looking guarded. An account the responsible
    # party never sees is no account at all.
    _seal = rep.get("seal") or []
    if _seal:
        ss = ["The deterministic pre-pass normalised your spec in place before the probe ran.",
              "**Only additive** — it never overwrites a key you wrote. Every change is listed:",
              ""]
        ss += ["· [%s] %s" % (x.get("kind"), x.get("note")) for x in _seal[:20]]
        if len(_seal) > 20:
            ss.append("… %d more (this is a sample, not the list)" % (len(_seal) - 20))
        ss += ["", "`session_fields` entries that begin \"spec has no auth.account_entity\" are the",
               "**most serious thing on this page**: every `$actor.<col>` guard in the spec has",
               "nowhere to resolve against, so those walls do not exist at runtime — and L2 will",
               "still look calm, because a wall that cannot be evaluated simply never fires.",
               "Pick the account entity and declare `auth.account_entity`."]
        seal_s = "\n".join(ss)
    else:
        seal_s = "(nothing — the pre-pass changed nothing in your spec)"
    _nm = (rep.get("no_message") or [])
    if _nm:
        s2 = (s2 or "") + (
            "\n\n**%d tools declare a wall but carry no refusal text.** When one of these refuses, "
            "the runtime answers with its own generic string — not in the language the caller "
            "reads, and silent about *which* wall stopped it and what would satisfy it.\n\n"
            "Two places work, and the runtime reads them in this order when a precondition "
            "is not satisfied: **(1) `guards.messages.precondition`** — one sentence for the "
            "whole tool; **(2) a `message` on the individual precondition** — one per wall, "
            "used when there is no tool-level one. Prefer (2) when the tool has several walls "
            "that fail for different reasons; a tool with one wall is fine with (1).\n\n"
            "⚠ The key for a failed precondition is **`precondition`**. The other keys in "
            "`guards.messages` are for different refusals and will not be reached here: "
            "`not_found` (the row does not exist), `fk` / `fk_missing`, `guard_last`, "
            "`on_child`, `off_panel`, `multi`, `confirm`. There is no `auth` key — a "
            "not-logged-in refusal comes out of the auth layer, not from here.\n\n"
            "**A refusal text is not a label — it is the sentence the caller reads and acts on.** "
            "So write it from two things: (a) **what this particular tool does**, and (b) **the "
            "words this application itself uses** for those entities and roles. Best source: the "
            "operation's own `ref_code`, which usually contains the real error string the code "
            "raises — prefer that wording over anything invented. Where the code has no string, "
            "say the condition in the app's own vocabulary and, when there is one, the way out.\n\n"
            "Good: `\"Only the board owner can archive a board.\"` · `\"This invoice is already "
            "paid; reopen it before adding a line.\"` · `\"That project has no active sprint.\"`\n"
            "Useless: `\"Permission denied.\"` · `\"Precondition failed.\"` · `\"Not allowed.\"` — "
            "one generic sentence copied across N tools satisfies nothing; it is the same as "
            "having written none, and it is worse because it looks answered.\n\n"
            "This is an addition only: never remove or weaken a wall to make a line here go "
            "away.\n\n%s"
            % (len(_nm), "  " + ", ".join(_nm[:40]) + (" …" if len(_nm) > 40 else "")))
    return s0, s1, s2, s3, cov, seal_s


def brief0(rep):
    """Results of `probe⁰` -> **the copy given to the agent** (the full report is saved
    separately, for us).

    `probe⁰` runs on det's candidate spec, which **the agent has not touched yet**. So its
    findings fall into two classes, and only one belongs to the agent:

      Structural (L0)   required family keys, phantom columns, missing pk, dangling fk ... all
                        about **the completeness of collect and det's translation**. The agent
                        cannot open the source code and cannot fix these — that is the job of the
                        collector-side contract check and its top-up loop. Giving them to the agent
                        only makes it "fix" things it cannot fix, or worse: change correct
                        declarations just to make the report clean.
      Semantic (L2/L3)  "this tool is declared as a write, but calling it left the world
                        unchanged", "a wall is declared, but the violation was not refused" —
                        these ask **whether what this spec says is true**, which the agent can
                        judge and change.

    ⚠ One more thing must be made clear: the candidate spec **has no auth block** (the account
    entity is chosen by the agent), so the probe cannot log in, a batch of tools stop at guarded
    and read tools return empty. **That is not a defect, it is the condition of this round.**
    Without saying so, the agent would try to "fix" a set of artificially depressed numbers.
    """
    l2 = rep.get("l2") or {}
    l3 = rep.get("l3") or {}
    out = ["# Probe on the pre-pass's candidate spec (before you touched it)", "",
           "**Not logged in.** The candidate spec has no `auth` block yet — you pick the account",
           "entity — so the probe could not sign in. A pile of `guarded` and empty reads is the",
           "condition of this run, **not a defect**. Do not try to fix it.", "",
           "Structural findings are deliberately **not** included: they are about how complete the",
           "mined atoms are and how the pre-pass translated them, which is the collector's",
           "feedback loop, not yours. What follows is only what is about **what this spec claims**.",
           ""]
    c = l2.get("counts") or {}
    out += ["## Tools that did nothing / touched the wrong table / could not be read", "",
            "counts: %s" % json.dumps(c, ensure_ascii=False), ""]
    for k, lbl in (("no_op", "`no_op` — the call succeeded and **the world did not change**"),
                   ("wrong_entity", "`wrong_entity` — something changed, but not the table it declares"),
                   ("bad_exec_spec", "`bad_exec_spec` — the runtime cannot read this `exec_spec`")):
        v = l2.get(k) or []
        if v:
            out += ["%s:" % lbl, "  " + ", ".join(v[:60]), ""]
    wm = l3.get("wall_missing") or []
    if wm:
        out += ["## Walls that did not fire", "",
                "The pre-pass compiled these from behaviour edges. A deliberate violation was",
                "**not** refused — so either the guard is on the wrong tool / in the wrong shape,",
                "or the wall does not exist in the real code. **A wall you cannot evidence must go.**", ""]
        out += ["· %s — declared a %s wall, the violation was NOT refused" % (a, b) for a, b in wm[:60]]
        out += [""]
    if not any(l2.get(k) for k in ("no_op", "wrong_entity", "bad_exec_spec")) and not wm:
        out += ["(Nothing in this class — the candidate spec's claims held up as far as the probe",
                "could drive it without a login.)", ""]
    return "\n".join(out)


def _wrote_rate(rep):
    w = (rep.get("l2") or {}).get("counts", {}).get("wrote", 0)
    n = rep.get("writable") or 0
    return (w / n) if n else None


def no_message_tools(spec):
    u"""Tools that have guards but not a single refusal text -> list of tool names.

    **The wall's text is the training signal itself** — build_spec.md devotes a whole section to
    this, and the agent complied 92.6% of the time. But nobody ever told it about the remaining
    7.4%: the feedback template never mentioned messages, and neither the probe nor the gate
    looked at them. This is not "judged correctly but no way out given"; **the judging layer never
    looked at all**, which is one step worse. When these tools refuse, they fall back to the
    runtime's default string, which is not in the language of the agent's (English) prompt.

    The criterion is purely structural: having it in any of three places counts —
    `guards.messages` / `exec_spec.messages` / `message` on an individual precondition. It only
    rewards "adding a field": it cannot break a good tool, and there is no "delete it and go
    green" shortcut (deleting the guard is a bigger violation).
    """
    out = []
    for t in ((spec or {}).get("tools") or []):
        g = t.get("guards") or {}
        pcs = g.get("preconditions") or []
        if not pcs:
            continue
        # ⚠ **Only count the two places the runtime actually reads when a precondition is
        #   refused** (see runtime.py):
        #     msgs.get("precondition")  or  per-precondition message/_msg  or  built-in fallback
        # The other keys in `guards.messages` (auth / fk / not_found / required ...) belong to
        # other refusal paths and are **never read** when a precondition fails. This used to say
        # "non-empty messages counts" — 12x too loose: one app (itflow) has 9 other keys and no
        # precondition; the loose criterion counted 0, the strict one 459. As a result, when it
        # was used as a gate it hid 92% of the gaps from the agent (89 of 228 repos showed "no
        # todo"). Lesson: one fact gets exactly one criterion.
        _m = dict((t.get("exec_spec") or {}).get("messages") or {})
        _m.update(g.get("messages") or {})
        if _m.get("precondition"):
            continue
        flat = [x for grp in pcs for x in (grp if isinstance(grp, list) else [grp])]
        # ⚠ Accept both keys: `message` is the authoritative human-written name, `_msg` is the
        # internal name after norm_preconditions / from_state normalisation. Checking only the
        # former would falsely report every IR-compiled tool as missing its text.
        if any(isinstance(x, dict) and (x.get("message") or x.get("_msg")) for x in flat):
            continue
        out.append(t.get("tool"))
    return out


def loop_drivers(rep, baseline=None):
    """-> {name: count}. Non-empty means run another round, **but once the rounds are used up,
    accept the result**.

    Kept separate from the hard gate on purpose:
      · hard gate = **must be true**, otherwise downstream task generation cannot use this spec
        (no verifier can be drafted, no witness can be produced)
      · loop driver = **worth one more try**, but "delete this wall" is also a legitimate answer —
        if the agent judges the wall is real and the probe just cannot build a violating scenario,
        more rounds only burn turns and push it to delete correct guards
    """
    out = {}
    n = (rep.get("l0") or {}).get("n_err", 0)
    if n:
        out["l0_err"] = n
    wm = len((rep.get("l3") or {}).get("wall_missing") or [])
    if wm:
        out["fake_wall"] = wm
    we = (rep.get("l2") or {}).get("counts", {}).get("wrong_entity", 0)
    if we:
        # The verifier checks the table as declared; a wrong declaration ruins the whole task —
        # same severity as a fake wall
        out["wrong_entity"] = we
    # `no_op` / `error` were originally **not loop drivers** — the gate only asks ">=1 write +
    # >=1 read" and breaks once passed, so the agent never once saw that the probe measured these
    # tools as doing nothing. Measured across the library: 440 tools (no_op 334 / error 106).
    # Checking each exec_spec: 26% have written columns that do not match the input panel (the
    # agent can fix this), 57% have matching columns and panel but the probe could not lay down
    # that row, 17% were never told by collection what they write. At least the first class is
    # something the agent has the information and authority to fix, and it was never told.
    _nm = len(rep.get("no_message") or [])
    if _nm:
        out["guard_without_message"] = _nm
    # ⚠ **Off by default.** After adding it we only ran a small batch of 11 repos: 2 improved,
    # 8 unchanged, 1 regressed (one repo cut no_op from 9 to 6 by deleting 3 tools, which the
    # guard caught and rolled back). The sample is too small and already shows a "delete it and
    # go green" tendency, so it stays out of the loop until validated — forcing the agent to touch
    # something it mostly cannot fix costs more than it gains (57% of no_op are rows the probe
    # could not lay down, not mistakes by the agent). To validate: LEGOENV_DRV_NOOP=1.
    if os.environ.get("LEGOENV_DRV_NOOP") == "1":
        _no = len((rep.get("l2") or {}).get("no_op") or [])
        if _no:
            out["no_op"] = _no
        _er = (rep.get("l2") or {}).get("counts", {}).get("error", 0)
        if _er:
            out["error"] = _er
    be = (rep.get("l2") or {}).get("counts", {}).get("bad_exec_spec", 0)
    if be:
        # The runtime throws when reading this exec_spec — the tool is dead and every call returns
        # an error. Same nature as "guard without evidence": independent of how hard the repo is,
        # it is simply done or not, so an absolute criterion is fine.
        # **Not a hard gate**: what is broken is individual tools, not the whole world (mcp_env
        # catches exceptions per call; a broken tool just returns an error). Rejecting a whole repo
        # over 7/47 tools is over-blocking.
        out["exec_spec_unreadable"] = be
    ne = (rep.get("l0") or {}).get("n_no_evidence", 0)
    if ne:
        # The prompt states plainly "a wall you cannot evidence must not be written". **Independent
        # of how hard the repo is**, it is simply done or not — so this one can use an absolute
        # criterion. Two measured runs gave 0/20 and 19/19: highly discriminative.
        out["guard_without_evidence"] = ne
    if baseline is not None:
        a, b = _wrote_rate(rep), _wrote_rate(baseline)
        if a is not None and b is not None and a < b:
            # **No absolute threshold**, only "is it worse than the mechanical translation". A
            # threshold creates pressure to "bend the spec to hit the number"; "don't be worse
            # than the machine" is a safe direction, and hard repos have low baselines anyway, so
            # it normalises itself.
            out["wrote_rate_below_baseline"] = "%.0f%% < %.0f%%" % (100 * a, 100 * b)
    return out


def gate(spec, rep):
    """-> (ok, why). **Must pass**: L1 passes + >=1 write tool really changed the world + a
    read/search tool **exists** in the spec.

    Why the read criterion is "exists" rather than "the probe got content back":
    the original criterion `returned >= 1` did not measure "does this repo have search
    capability", but "did **my throwaway synthetic seed** make some read tool return something".
    In practice it collapsed three completely different things into the same failure:
      · genuinely no read tool (aimeos / firezone / sentry ...)             <- only this should fail
      · read tools exist, but return empty on the synthetic seed (documenso / tolgee-platform)
      · **47 read tools exist, but the probe hit permission walls on all of them (killbill: guarded 110)**
    "Exists" is something det can judge precisely; "can it find anything" needs real data, which
    is the job of downstream task generation.

    There used to be an l1_own here (validating the agent's own smoke seed) — removed; see
    build_probe.probe for the reason.
    """
    # There used to be "shape error -> refuse delivery" here. Removed: mcp_env catches exceptions
    # per call and returns {"error": ...}, so a tool that throws is just a broken tool during task
    # generation (downstream agents report it and can repair it), not a disaster.
    # Rejecting a whole repo over 7/47 tools is exactly the kind of over-blocking already
    # corrected several times.
    # Where it goes now: L2 really calls each tool -> throws are recorded as error -> go into the
    # feedback round for whoever wrote it to fix.
    if not (rep.get("l1") or {}).get("ok"):
        return False, "L1 failed: %s" % (rep.get("l1") or {}).get("why")
    c = (rep.get("l2") or {}).get("counts") or {}
    if not c:
        return False, "L2 did not run"
    if c.get("wrote", 0) < 1:
        return False, "no write tool actually changed the world"
    n_read = sum(1 for t in (spec.get("tools") or [])
                 if PROBE._is_read(str(t.get("family") or "")))
    if n_read < 1:
        return False, "the repo has no read/search tool — tasks have no way to \"find\" a target"
    return True, ""


def promote(repo, spec, log=print):
    """Spec that passed the gate -> repo_specs/<repo>.spec.json (atomic write). -> written path.

    **Specs that fail the gate are not written**: this directory is the **only** spec source for
    downstream task generation; once a spec that cannot run enters the cache, every downstream
    task gets it, and it is never rebuilt."""
    os.makedirs(REPO_SPEC_CACHE, exist_ok=True)
    p = os.path.join(REPO_SPEC_CACHE, "%s.spec.json" % repo)
    tmp = "%s.tmp.%d" % (p, os.getpid())
    spec = dict(spec)
    spec["env_id"] = repo            # downstream prefixes by env_id, so it must equal repo
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
    os.replace(tmp, p)
    log("[build:%s] cached %s" % (repo, p))
    return p


def build(repo, collect_path, out_dir, bridge=None, log=print, timeout=3600):
    """-> {"ok", "spec", "report", "why"}. If the gate passes, also writes to the repo_specs/ cache."""
    work = os.path.join(out_dir, repo)
    os.makedirs(work, exist_ok=True)
    t0 = time.time()

    # ── ① prep ──
    d = json.load(open(collect_path, encoding="utf-8"))
    raw, prep_rep = PREP.prep(d)
    raw_p = os.path.join(work, "spec.raw.json")
    json.dump(raw, open(raw_p, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(prep_rep, open(os.path.join(work, "prep_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log("[build:%s] prep: %d entities / %d candidate tools / %d with guards"
        % (repo, prep_rep["out"]["entities"], prep_rep["out"]["tools"],
           prep_rep["out"]["tools_with_preconditions"]))

    # Run the probe over the candidate pool first, so the agent's very first brief carries
    # evidence — instead of asking it to re-check a pile of fallbacks that det itself never
    # validated.
    rep0 = PROBE.probe(raw)
    json.dump(rep0, open(os.path.join(work, "build_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # The full report is **for us** (baseline, accounting); the agent gets a filtered one —
    # see the brief0 docstring.
    rep0_p = os.path.join(work, "probe0_for_agent.md")
    io_open = open(rep0_p, "w", encoding="utf-8")
    io_open.write(brief0(rep0))
    io_open.close()
    log("[build:%s] probe (candidate): L0 err=%d L1=%s L2=%s"
        % (repo, rep0["l0"]["n_err"], rep0["l1"]["ok"], (rep0.get("l2") or {}).get("counts")))

    # ── ② agent ──
    out_p = os.path.join(work, "spec.draft.json")
    shutil.copy(collect_path, os.path.join(work, "collect.json"))
    prompt = _fill(open(PROMPT, encoding="utf-8").read(),
                   RAW=raw_p, COLLECT=os.path.join(work, "collect.json"),
                   REPORT=rep0_p, OUT=out_p)
    r = CC.run_cc(prompt, cwd=work, timeout=timeout, bridge=bridge, tag="build_%s" % repo, log=log)
    sid = r.get("session_id")
    # Persist it: re-running the feedback round across runs, or a standalone dev feedback round,
    # both need it. Keeping it as a local variable means the session is lost once a run ends —
    # and repos whose feedback round was eaten by a crash are exactly the ones that most need to
    # redo just that round.
    json.dump({"session_id": sid, "repo": repo, "turns": r.get("num_turns"),
               "bridge": bridge, "ts": time.strftime("%Y-%m-%d %H:%M:%S")},
              open(os.path.join(work, "agent_session.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log("[build:%s] agent: ok=%s turns=%s sid=%s %.1fmin"
        % (repo, r.get("ok"), r.get("num_turns"), str(sid)[:8], (time.time() - t0) / 60))
    if not os.path.exists(out_p):
        return {"ok": False, "why": "agent did not produce spec.draft.json", "report": rep0}

    # ── ③④ probe + feedback round (det finds faults, whoever wrote it fixes them) ──
    rep, spec, reps = None, None, []
    for rnd in range(R_BUILD + 1):
        try:
            spec = json.load(open(out_p, encoding="utf-8"))
        except Exception as ex:
            return {"ok": False, "why": "draft is not valid JSON: %s" % ex, "report": rep or rep0}
        # det normalisation: only carries over what det can derive mechanically and the agent
        # would only drop if asked to copy it; additive only, never overwrites, fully accounted.
        # **Must run before the probe** — otherwise the probe cannot resolve $session.<col> and
        # reports wiring det itself failed to connect as the agent's write failure. See the
        # PREP.seal docstring.
        seal_notes = PREP.seal(spec, raw)
        for _k, _t in seal_notes:
            log("[build:%s] r%d seal/%s: %s" % (repo, rnd, _k, _t))
        rep = PROBE.probe(spec)
        rep["no_message"] = no_message_tools(spec)
        if seal_notes:
            rep["seal"] = [{"kind": k, "note": t} for k, t in seal_notes]
        json.dump(rep, open(os.path.join(work, "build_report_r%d.json" % rnd), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
        ok, why = gate(spec, rep)
        drv = loop_drivers(rep, rep0)
        if reps is not None:
            reps.append(rep)
        log("[build:%s] r%d: L0 err=%d L1=%s L2=%s gate=%s%s%s"
            % (repo, rnd, rep["l0"]["n_err"], rep["l1"]["ok"],
               (rep.get("l2") or {}).get("counts"), ok, "" if ok else " (%s)" % why,
               " todo=%s" % drv if drv else ""))
        if ok and not drv:
            break
        if rnd == R_BUILD:
            break
        if not sid:
            log("[build:%s] no session_id, feedback round skipped (**a skip is an account, not a pass**)" % repo)
            break
        s0, s1, s2, s3, cov, sl = _brief(rep, spec, rep0, raw)
        msg = _fill(open(FEEDBACK, encoding="utf-8").read(),
                    L0=s0, L1=s1, L2=s2, L3=s3, COVERAGE=cov, SEAL=sl, OUT=out_p)
        rr = CC.resume_cc(sid, msg, cwd=work, timeout=timeout, bridge=bridge,
                          tag="build_fb_%s_r%d" % (repo, rnd), log=log)
        json.dump({"session_id": sid, "repo": repo, "last_feedback_round": rnd,
                   "bridge": bridge, "ts": time.strftime("%Y-%m-%d %H:%M:%S")},
                  open(os.path.join(work, "agent_session.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        if not rr.get("ok"):
            log("[build:%s] r%d feedback-round resume failed, stopping at the current result" % (repo, rnd))
            break

    ok, why = gate(spec, rep)
    res = {"ok": ok, "why": why, "spec": spec, "report": rep,
           "minutes": round((time.time() - t0) / 60, 1)}
    # ⚠ The baseline is **a floor, not a standard**. rep0 runs on spec.raw.json, which **has no
    # auth yet** (the agent picks the account entity), so the probe cannot log in, a batch of
    # tools stop at guarded, and the baseline wrote rate is depressed. It only answers "is it
    # worse than the mechanical translation", **not "is it good enough"** — "above baseline" is
    # not a quality verdict. Measuring "good enough" needs another anchor, which we do not have.
    res["baseline"] = {
        "wrote_rate": round(_wrote_rate(rep0) or 0, 3),
        "draft_wrote_rate": round(_wrote_rate(rep) or 0, 3),
        "note": "candidate baseline runs on the raw spec without auth and is depressed; it is a floor, "
                "not a standard: \"above baseline\" != \"good enough\"",
    }
    # Whatever is still unresolved after all rounds -> **record it, do not discard the repo**.
    # Permanently skipping a 30-tool repo over 2 leftovers throws away usable material.
    drv = loop_drivers(rep, rep0)
    if drv:
        res["residual"] = drv
    # r0 -> r1 diff: **what this feedback round actually bought**. For us, not for the agent —
    # whether the feedback round is worth its turn can only be told by this number.
    if ok:
        try:
            res["cached"] = promote(repo, spec, log)
        except Exception as ex:
            log("[build:%s] caching failed: %s" % (repo, str(ex)[:120]))
    if len(reps) >= 2:
        def c(x):
            return dict((x.get("l2") or {}).get("counts") or {})
        a, b = c(reps[0]), c(reps[-1])
        res["feedback_delta"] = {
            "l0_err": [reps[0]["l0"]["n_err"], reps[-1]["l0"]["n_err"]],
            "wall_missing": [len((reps[0].get("l3") or {}).get("wall_missing") or []),
                             len((reps[-1].get("l3") or {}).get("wall_missing") or [])],
            "l2": {k: [a.get(k, 0), b.get(k, 0)]
                   for k in sorted(set(a) | set(b)) if a.get(k, 0) != b.get(k, 0)},
        }
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Stage 2: collect JSON -> executable repo spec")
    ap.add_argument("repo", help="repository slug (becomes env_id)")
    ap.add_argument("--collect", required=True, help="path to the stage-1 collect/<repo>.json")
    ap.add_argument("--run", required=True, help="run directory; work files go to <run>/build/<repo>/")
    ap.add_argument("--spec-dir", default=None,
                    help="where passing specs are written (default <run>/repo_specs)")
    ap.add_argument("--bridge", default=None, help="bridge base URL (default $BRIDGE_URL)")
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    set_spec_dir(a.spec_dir or os.path.join(a.run, "repo_specs"))
    res = build(a.repo, a.collect, os.path.join(a.run, "build"), bridge=a.bridge, timeout=a.timeout)
    print(json.dumps({k: v for k, v in res.items() if k != "spec"},
                     ensure_ascii=False, indent=1)[:3000])
