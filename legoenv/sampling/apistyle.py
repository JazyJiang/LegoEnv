#!/usr/bin/env python3
"""Deterministic local API catalog and routing.
Includes BM25 ranking code Copyright 2026 Zapier, Inc. SPDX-License-Identifier: MIT.
Original provenance is recorded in THIRD_PARTY_NOTICES.md.
"""
import json, math, os, re, urllib.parse
import mcp_server
HERE = os.path.dirname(os.path.abspath(__file__))

def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, treating underscores as word separators."""
    return re.findall('[a-z0-9]+', text.lower().replace('_', ' '))

class BM25Scorer:
    """BM25 ranking over a fixed list of documents (k1=1.5, b=0.75, Robertson-Sparck Jones IDF)."""

    def __init__(self, docs: list[str], k1: float=1.5, b: float=0.75) -> None:
        self.k1 = k1
        self.b = b
        self._tokenized: list[list[str]] = [tokenize(doc) for doc in docs]
        n = len(self._tokenized)
        self._avgdl = sum((len(d) for d in self._tokenized)) / n if n else 1.0
        df: dict[str, int] = {}
        for doc in self._tokenized:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1
        self._idf: dict[str, float] = {term: math.log((n - freq + 0.5) / (freq + 0.5) + 1) for term, freq in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        result = []
        for doc_tokens in self._tokenized:
            dl = len(doc_tokens)
            score = 0.0
            for term in terms:
                idf = self._idf.get(term, 0.0)
                if idf == 0.0:
                    continue
                tf = doc_tokens.count(term)
                score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self._avgdl))
            result.append(score)
        return result

    def top_k(self, query: str, k: int=10) -> list[int]:
        scored = [(s, i) for i, s in enumerate(self.scores(query)) if s > 0]
        scored.sort(key=lambda x: -x[0])
        return [i for _, i in scored[:k]]
PRODUCT_BASE = {'akaunting': 'https://app.akaunting.com/api/v1', 'budibase': 'https://yourtenant.budibase.app/api/public/v1', 'chatwoot': 'https://app.chatwoot.com/api/v1', 'cloudreve': 'https://yourinstance.cloudreve.org/api/v4', 'directus': 'https://yourproject.directus.app/api/v1', 'easyappointments': 'https://yourinstance.easyappointments.org/index.php/api/v1', 'espocrm': 'https://yourinstance.espocrm.com/api/v1', 'ever_gauzy': 'https://api.gauzy.co/api/v1', 'ghost': 'https://yoursite.ghost.io/ghost/api/admin', 'gladys': 'https://yourhome.gladysassistant.com/api/v1', 'librechat': 'https://yourinstance.librechat.ai/api/v1', 'libredesk': 'https://yourinstance.libredesk.io/api/v1', 'listmonk': 'https://yourinstance.listmonk.app/api/v1', 'mantisbt': 'https://yourinstance.mantishub.io/api/rest', 'mastodon': 'https://mastodon.social/api/v1', 'misskey': 'https://misskey.io/api/v1', 'openmeetings': 'https://yourinstance.openmeetings.org/openmeetings/services/v1', 'opensign': 'https://app.opensignlabs.com/api/v1', 'outline': 'https://app.getoutline.com/api/v1', 'planka': 'https://yourinstance.planka.cloud/api/v1', 'stalwart': 'https://yourinstance.stalw.art/jmap/v1', 'vikunja': 'https://try.vikunja.io/api/v1', 'zulip': 'https://yourorg.zulipchat.com/api/v1'}

def product_of(ns):
    return ns[:-3] if ns.endswith('_ab') else ns

def base_of(product):
    return PRODUCT_BASE.get(product) or f"https://api.{product.replace('_', '-')}.com/v1"

def short_entity(e):
    return e.split('__', 1)[1] if isinstance(e, str) and '__' in e else e or ''
_VERBS = set('get list create update delete remove add set send fetch find search revoke invite register count\ngenerate reset upload download export import mark move copy archive unarchive restore publish unpublish approve\nreject assign unassign close open reopen cancel submit sync toggle enable disable change edit post put patch read\nview check verify request accept decline join leave start stop pin unpin follow unfollow mute unmute block unblock\nsubscribe unsubscribe lock unlock run trigger test duplicate clone merge convert transfer link unlink attach detach\nschedule book sign log login logout signin signout upsert bulk batch clear save share resolve react reply forward\nstar unstar like unlike favourite unfavourite report calculate process apply complete refresh rename reorder rotate\nvalidate void pay refund issue deactivate activate suspend unsuspend ban unban promote demote grant deny snooze\nunsnooze notify broadcast query lookup retrieve show describe write insert append increment decrement reserve\nrelease confirm destroy'.split())
_PARTICLES = {'in', 'out', 'up', 'off', 'on'}
_NOPLURAL = {'auth', 'self', 'me', 'health', 'metadata', 'info', 'status', 'server', 'maintenance', 'search', 'data', 'media', 'news', 'feedback', 'analytics', 'stats', 'admin', 'settings', 'api', 'sms', 'jmap', 'misc', 'staff', 'people', 'personnel', 'equipment', 'inventory', 'software', 'hardware', 'mail', 'email', 'calendar', 'workspace'}
_NOPLURAL -= {'email', 'workspace', 'calendar'}

def _plural(w):
    if w in _NOPLURAL or w.endswith('s') or (not w[-1:].isalpha()):
        return w
    if w.endswith('y') and len(w) > 1 and (w[-2] not in 'aeiou'):
        return w[:-1] + 'ies'
    if w.endswith(('x', 'ch', 'sh', 'z')):
        return w + 'es'
    return w + 's'

def _split_name(suffix, ent_short):
    """tool name (without ns__) -> (resource tokens, action tokens)."""
    toks = [t for t in suffix.lower().split('_') if t]
    if not toks:
        return (['misc'], [])
    el = (ent_short or '').lower()
    if el:
        for k in range(len(toks) - 1, 0, -1):
            if ''.join(toks[:k]) in (el, el + 's', el + 'es'):
                return (toks[:k], toks[k:])
    if len(toks) >= 2 and toks[0] in _VERBS and (toks[1] in _PARTICLES):
        return (toks[2:] or ['auth'], toks[:2])
    if len(toks) >= 2 and toks[0] in _VERBS:
        i = 1
        while i < len(toks) - 1 and (toks[i] in _VERBS or toks[i] in ('or', 'and')):
            i += 1
        return (toks[i:], toks[:i])
    return (toks[:1], toks[1:])

def method_of(t):
    """HTTP method from the spec tool's op (family when op is absent)."""
    fam = t.get('family') or ''
    base = fam.split('.')[0]
    op = t.get('op')
    if base in ('guard', 'auth'):
        return 'POST'
    if op in ('read', 'search'):
        return 'GET'
    if op == 'create':
        return 'POST'
    if op == 'update':
        return 'PATCH'
    if op == 'delete':
        return 'DELETE'
    if op is None:
        if base == 'search' or fam == 'crud.fetch':
            return 'GET'
        if fam == 'crud.insert':
            return 'POST'
        if base == 'update':
            return 'PATCH'
        if fam in ('crud.delete', 'crud.soft_delete'):
            return 'DELETE'
    return 'POST'
_CANON = {('POST', False): {'create', 'add', 'new', 'insert'}, ('GET', False): {'list', 'fetchall', 'findall', 'getall', 'all', 'index'}, ('GET', True): {'get', 'find', 'read', 'fetch', 'show', 'findone', 'view', 'retrieve', 'detail', 'details'}, ('PATCH', True): {'update', 'edit', 'patch', 'modify'}, ('DELETE', True): {'delete', 'destroy', 'remove'}}
_DEFAULT_ACT = {('GET', False): 'list', ('GET', True): 'get', ('POST', False): 'create', ('POST', True): 'create', ('PATCH', False): 'update', ('PATCH', True): 'update', ('DELETE', False): 'delete', ('DELETE', True): 'delete'}
_TYPE_OK = ('GET', 'PATCH', 'DELETE', 'POST')

def coerce_to_dict(value):
    """coerce_to_dict: deterministic local endpoint catalog operation."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError(f'expected a JSON object string, got {type(value).__name__}')
    v = json.loads(value)
    if not isinstance(v, dict):
        raise ValueError(f'expected a JSON object, got {type(v).__name__}')
    return v

def _err(code, message):
    return json.dumps({'error': {'code': code, 'message': message}}, ensure_ascii=False)

class Catalog:
    """The endpoint catalog of one pack's world."""

    def __init__(self, spec):
        self.spec = spec
        self.spec_tools = {t['tool']: t for t in spec.get('tools', [])}
        mcp = mcp_server.build_tools(spec)
        nss = sorted({t['name'].split('__', 1)[0] for t in mcp if '__' in t['name']})
        self.ns_base, used_bases = ({}, {})
        for ns in nss:
            b = base_of(product_of(ns))
            if b in used_bases:
                b = b.replace('://', f"://{ns.replace('_', '-')}.", 1)
            used_bases[b] = ns
            self.ns_base[ns] = b
        raw = []
        for t in mcp:
            name = t['name']
            ns, suffix = name.split('__', 1) if '__' in name else ('', name)
            st = self.spec_tools.get(name, {})
            m = method_of(st)
            props = (t.get('inputSchema') or {}).get('properties') or {}
            req = list((t.get('inputSchema') or {}).get('required') or [])
            fam = st.get('family') or ''
            use_id = 'id' in req and m in _TYPE_OK and (st.get('op') != 'create') and (fam.split('.')[0] not in ('guard', 'auth')) and (fam != 'crud.insert')
            res_t, act_t = _split_name(suffix, short_entity(st.get('entity')))
            res_seg = '-'.join(res_t[:-1] + [_plural(res_t[-1])])
            act_seg = '-'.join(act_t)
            long_ = '/' + res_seg + ('/{id}' if use_id else '') + ('/' + act_seg if act_seg else '')
            short = None
            if act_seg and act_seg in _CANON.get((m, use_id), ()):
                short = '/' + res_seg + ('/{id}' if use_id else '')
            raw.append(dict(tool=name, ns=ns, suffix=suffix, method=m, props=props, required=req, use_id=use_id, res_t=res_t, act_t=act_t, res_seg=res_seg, act_seg=act_seg, long=long_, short=short, description=t.get('description') or ''))
        raw.sort(key=lambda r: r['tool'])
        key = lambda r, tpl: (r['ns'], r['method'], tpl)
        cnt = {}
        for r in raw:
            cnt[key(r, r['long'])] = cnt.get(key(r, r['long']), 0) + 1
        for r in raw:
            if cnt[key(r, r['long'])] > 1:
                r['long'] = '/' + r['suffix'].lower().replace('_', '-') + ('/{id}' if r['use_id'] else '')
                r['short'] = None
                r['form'] = 'fallback'
            r['tpl'] = r['long']
            r.setdefault('form', 'long')
        taken = {key(r, r['tpl']) for r in raw}
        assert len(taken) == len(raw), 'endpoint collision after fallback'
        for r in raw:
            if r['short'] and key(r, r['short']) not in taken:
                taken.discard(key(r, r['tpl']))
                r['tpl'] = r['short']
                r['form'] = 'short'
                taken.add(key(r, r['tpl']))
        self.endpoints, self.by_tool, ids = ([], {}, set())
        for r in raw:
            product = product_of(r['ns'])
            base = self.ns_base.get(r['ns']) or base_of(product)
            eid = f"{product}.{r['suffix']}"
            if eid in ids:
                eid = f"{r['ns']}.{r['suffix']}"
            ids.add(eid)
            url = base + r['tpl']
            segs = [s for s in urllib.parse.urlsplit(url).path.split('/') if s]
            ep = dict(tool=r['tool'], ns=r['ns'], product=product, base=base, method=r['method'], url=url, tpl=r['tpl'], form=r['form'], id=eid, name=r['suffix'], segs=segs, host=urllib.parse.urlsplit(url).netloc.lower(), path_params=['id'] if r['use_id'] else [], props=r['props'], required=r['required'], description=r['description'], res_t=r['res_t'], act_t=r['act_t'])
            self.endpoints.append(ep)
            self.by_tool[r['tool']] = ep
        self._by_host = {}
        for ep in self.endpoints:
            self._by_host.setdefault(ep['host'], []).append(ep)
        self._suffix_ns = {}
        for ep in self.endpoints:
            if ep['ns']:
                self._suffix_ns.setdefault(ep['tool'].split('__', 1)[1], []).append(ep['ns'])
        alt = '|'.join((re.escape(n) for n in sorted(self.ns_base, key=len, reverse=True))) or '(?!x)x'
        self._re = re.compile('(?P<full>(?<![\\w{$])(?P<ns>' + alt + ')__(?P<suf>[A-Za-z0-9_]*))|(?P<bare>(?<![\\w/.{$@-])[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![\\w@]))')
        self._re_full = re.compile('(?<![\\w{$])(?P<ns>' + alt + ')__(?P<suf>[A-Za-z0-9_]*)')
        self._auth_tool = {}
        for ns in self.ns_base:
            a = [n for n, t in self.spec_tools.items() if n.startswith(ns + '__') and (t.get('family') or '').startswith('guard.auth')]
            if len(a) == 1:
                self._auth_tool[ns] = a[0]
        self.records, lines = ([], [])
        for ep in self.endpoints:
            ep['description_api'] = self.rewrite(ep['description'], ctx_ns=ep['ns'])
            rec = self._record(ep)
            self.records.append(rec)
            desc_parts = [rec['description']] + [p['description'] for p in rec['parameters'].values() if p.get('description')]
            searchable = ' '.join(filter(None, desc_parts))
            ipath = ep['product'] + '/' + '/'.join(ep['segs'])
            lines.append(re.sub('[\\t\\r\\n]+', ' ', '\t'.join([ep['product'], ep['id'], ep['method'], ipath])) + '\t' + re.sub('[\\t\\r\\n]+', ' ', searchable))
        self.lines = lines
        self.scorer = BM25Scorer(lines)
        self._names = {ep['name'].lower() for ep in self.endpoints}
        self._ids = {ep['id'].lower() for ep in self.endpoints}
        self._products = {ep['product'].lower() for ep in self.endpoints}

    def _record(self, ep):
        params, body = ({}, [])
        loc_rest = 'query' if ep['method'] in ('GET', 'DELETE') else 'body'
        for pn, pdef in ep['props'].items():
            loc = 'path' if pn in ep['path_params'] else loc_rest
            d = {'type': pdef.get('type', 'string')}
            if pdef.get('description'):
                d['description'] = self.rewrite(pdef['description'], ctx_ns=ep['ns'])
            d['required'] = pn in ep['required']
            d['location'] = loc
            if pdef.get('enum'):
                d['enum'] = pdef['enum']
            if isinstance(pdef.get('items'), dict) and pdef['items']:
                d['items'] = pdef['items']
            params[pn] = d
            if loc == 'body':
                body.append(pn + ('' if d['required'] else '?'))
        st = self.spec_tools.get(ep['tool'], {})
        ent = short_entity(st.get('entity')) or 'record'
        fam = (st.get('family') or '').split('.')[0]
        if fam in ('guard', 'auth'):
            resp = '{result: string}'
        elif ep['method'] == 'GET':
            resp = '{result: [%s]}' % ent
        elif st.get('op') == 'create':
            resp = "{result: {id}, entity: '%s'}" % ent
        else:
            resp = "{result, entity?: '%s'}" % ent
        rec = {'id': ep['id'], 'method': ep['method'], 'description': ep['description_api'], 'parameters': params}
        if body:
            rec['request'] = '{' + ', '.join(body) + '}'
        rec['response'] = resp
        rec['url'] = ep['url']
        return rec

    def _exact(self, query):
        """Endpoints the query names exactly: a short name (`email_set`; single-word names only when they are
        the whole query) or an endpoint id (stalwart.email_set). Ones whose product the query mentions first."""
        q = (query or '').strip().strip('`\'" ').lower()
        toks = [t.strip('`\'".,;:()[]') for t in re.findall('[^\\s]+', q)]
        names = {t for t in toks if t in self._names and ('_' in t or t == q)}
        ids = {t for t in toks if t in self._ids}
        if not names and (not ids):
            return []
        prods = set(toks) & self._products
        idx = [i for i, ep in enumerate(self.endpoints) if ep['name'].lower() in names or ep['id'].lower() in ids]
        return sorted(idx, key=lambda i: (self.endpoints[i]['product'] not in prods, i))

    def search(self, query, top_k=5, max_chars=None):
        """search: deterministic local endpoint catalog operation."""
        results, seen = ([], set())
        for i in self._exact(query) + self.scorer.top_k(query, k=top_k * 3):
            eid = self.endpoints[i]['id']
            if eid in seen:
                continue
            seen.add(eid)
            results.append(self.records[i])
            if len(results) >= top_k:
                break
        out = json.dumps({'results': results, 'count': len(results)})
        if max_chars and len(out) > max_chars and (len(results) > 1):
            n = len(results)
            while len(results) > 1 and len(out) > max_chars:
                results.pop()
                out = json.dumps({'results': results, 'count': len(results), 'note': f'{n - len(results)} more matching endpoints omitted (output size limit); use a more specific query or a smaller top_k'})
        return out

    def route(self, method, url):
        """route: deterministic local endpoint catalog operation."""
        u = urllib.parse.urlsplit((url or '').strip())
        host, path = (u.netloc.lower(), u.path)
        if not host and path and (not path.startswith('/')):
            host, _, rest = path.partition('/')
            host, path = (host.lower(), '/' + rest)
        segs = [urllib.parse.unquote(s) for s in path.split('/') if s]
        query = dict(urllib.parse.parse_qsl(u.query, keep_blank_values=True))
        best, path_hit = (None, False)
        for ep in self._by_host.get(host, ()):
            if len(ep['segs']) != len(segs):
                continue
            args, lit = ({}, 0)
            for a, b in zip(ep['segs'], segs):
                if a.startswith('{') and a.endswith('}'):
                    args[a[1:-1]] = b
                elif a == b:
                    lit += 1
                else:
                    break
            else:
                path_hit = True
                if ep['method'] == (method or '').upper() and (best is None or lit > best[2]):
                    best = (ep, args, lit)
        if best:
            ep, args, _ = best
            return (ep, args, query, None)
        if path_hit:
            return (None, None, None, _err(404, f"No handler for {(method or '').upper()} {path}"))
        return (None, None, None, _err(404, f'Unknown API URL: {url}'))

    @staticmethod
    def arg_columns(exec_spec, entity):
        """[(entity, column, arg)] for every {"$arg": arg} bound to a column anywhere in the exec_spec
        (row_key / lookup_by / set / fields / side effects); nested dicts carrying their own "entity" rebind it."""
        acc = []

        def walk(d, ent):
            if isinstance(d, dict):
                if isinstance(d.get('entity'), str):
                    ent = d['entity']
                for k, v in d.items():
                    if isinstance(v, dict) and set(v) == {'$arg'} and isinstance(v['$arg'], str):
                        acc.append((ent, k, v['$arg']))
                    else:
                        walk(v, ent)
            elif isinstance(d, list):
                for v in d:
                    walk(v, ent)
        walk(exec_spec or {}, entity)
        return acc

    def coerce_path(self, ep, args, state=None):
        """coerce_path: deterministic local endpoint catalog operation."""
        st = self.spec_tools.get(ep['tool'], {})
        es = st.get('exec_spec') or {}
        ent = es.get('entity') or st.get('entity')
        if not isinstance(ent, str):
            ent = None
        mapped = self.arg_columns(es, ent)
        state = state or {}
        out = {}
        for k, v in args.items():
            if isinstance(v, str) and re.fullmatch('-?\\d+', v):
                cols = [(e, c) for e, c, a in mapped if a == k] or [(ent, k)]
                vals = []
                for e, c in cols:
                    vals += [r.get(c) for r in (state.get(e) if isinstance(e, str) else None) or [] if isinstance(r, dict) and r.get(c) is not None]
                if vals and all((isinstance(x, str) for x in vals)):
                    out[k] = v
                elif vals and all((isinstance(x, int) and (not isinstance(x, bool)) for x in vals)):
                    out[k] = int(v)
                elif vals:
                    out[k] = v
                elif (ep['props'].get(k) or {}).get('type') in ('integer', 'number'):
                    out[k] = int(v)
                else:
                    out[k] = v
            else:
                out[k] = v
        return out

    def request_for(self, tool, args):
        """(tool, args) -> (method, url, params dict or None, body dict or None): how a client calls it."""
        ep = self.by_tool[tool]
        args = dict(args or {})
        url = ep['url']
        for p in ep['path_params']:
            if p in args:
                url = url.replace('{%s}' % p, urllib.parse.quote(str(args.pop(p)), safe=''))
        if ep['method'] in ('GET', 'DELETE'):
            return (ep['method'], url, args, None)
        return (ep['method'], url, None, args)

    def ref(self, tool):
        ep = self.by_tool[tool]
        return f"{ep['method']} {ep['url']}"

    def render(self, tool, res, ok, exc=False):
        ep = self.by_tool[tool]
        if ok:
            out = {k: v for k, v in res.items() if k != 'ok'} if isinstance(res, dict) else {'result': res}
            if isinstance(out.get('entity'), str):
                out['entity'] = short_entity(out['entity'])
            return self.scrub(json.dumps(out, ensure_ascii=False, default=str))
        msg = str(res.get('error') if isinstance(res, dict) else res)
        code = 500 if exc else self.error_code(tool, msg, res.get('refused_by') if isinstance(res, dict) else None)
        return _err(code, self.rewrite(msg, ctx_ns=ep['ns']))

    def error_code(self, tool, msg, refused_by=None):
        st = self.spec_tools.get(tool, {})
        msgs = (st.get('guards') or {}).get('messages') or {}
        is_ = lambda *ks: any((msgs.get(k) and msg == msgs[k] for k in ks))
        low = msg.lower()
        if refused_by == 'constraint' or is_('unique'):
            return 409
        if is_('auth') or msg.startswith('Not signed in') or ('sign in' in low and 'must' in low):
            return 401
        if is_('required') or msg.startswith('Missing required'):
            return 400
        if (st.get('family') or '').startswith('guard.auth') and (is_('precondition') or refused_by == 'guard'):
            return 401
        if is_('not_found') or ' not found' in low or 'no matching row' in low:
            return 404
        if is_('realm', 'precondition') or msg.startswith(('Insufficient permission', 'Precondition')):
            return 403
        if is_('fk', 'fk_missing', 'transition', 'on_child', 'guard_last', 'confirm', 'off_panel', 'multi'):
            return 422
        return 400

    def _name_text(self, tool, cur_ns):
        """A reference to an endpoint by its short name only (no method, URL or host): the model has to
        api_search it. Qualified with the product when the text is not already talking about that app."""
        ep = self.by_tool[tool]
        return f"`{ep['name']}`" if cur_ns == ep['ns'] else f"{ep['product']} `{ep['name']}`"

    def rewrite(self, text, ctx_ns=None, bare=True, stats=None):
        """Every literal tool reference -> the endpoint's short name in backticks (`email_set`, qualified as
        "stalwart `email_set`" when the text is not already about that app); ns__ prefixes -> the product
        name; ns__Entity -> Entity. bare=True also marks bare tool names (they already are short names)."""
        if not isinstance(text, str):
            text = ' '.join((str(x) for x in text)) if isinstance(text, (list, tuple)) else '' if text is None else str(text)
        if not text:
            return text
        st = stats if stats is not None else {}
        out, pos, cur = ([], 0, ctx_ns)
        rx = self._re if bare else self._re_full
        for m in rx.finditer(text):
            rep = None
            end = m.end()
            if m.groupdict().get('full') or not bare:
                ns, suf = (m.group('ns'), m.group('suf'))
                full = f'{ns}__{suf}'
                if not suf:
                    rep = product_of(ns)
                    tail = re.match('\\s*\\(\\s*' + re.escape(product_of(ns)) + '\\s*\\)', text[end:])
                    if tail:
                        end += tail.end()
                    st['prefix'] = st.get('prefix', 0) + 1
                elif full in self.by_tool:
                    rep = self._name_text(full, cur)
                    st['full'] = st.get('full', 0) + 1
                elif suf[:1].isupper():
                    rep = suf
                    st['entity'] = st.get('entity', 0) + 1
                elif re.search('log_?in|sign_?in', suf) and ns in self._auth_tool:
                    rep = self._name_text(self._auth_tool[ns], cur)
                    st['full_fixed'] = st.get('full_fixed', 0) + 1
                    st.setdefault('fixed', []).append(full)
                else:
                    rep = f'the {product_of(ns)} API'
                    st['unresolved'] = st.get('unresolved', 0) + 1
                    st.setdefault('unresolved_refs', []).append(full)
                cur = ns
            else:
                tok = m.group('bare')
                cands = self._suffix_ns.get(tok)
                if cands:
                    if cur not in cands and len(cands) > 1:
                        st['ambiguous'] = st.get('ambiguous', 0) + 1
                    rep = f'`{tok}`'
                    st['bare'] = st.get('bare', 0) + 1
            if rep is None:
                continue
            if text[m.start() - 1:m.start()] == '`' and text[end:end + 1] == '`' and rep.endswith('`'):
                rep = rep.replace('`', '')
            elif text[end:end + 1] == '(':
                rep += ' '
            out.append(text[pos:m.start()])
            out.append(rep)
            pos = end
        out.append(text[pos:])
        return ''.join(out)

    def scrub(self, s):
        """Observations: only unambiguous ns__ references are rewritten (row data is left alone)."""
        return self.rewrite(s, bare=False) if '__' in s else s

    def text_problems(self, text):
        """What a rewritten text must not contain: ns__-qualified tool names / prefixes, an endpoint short
        name outside backticks, any URL."""
        text = text or ''
        ns_refs = [m.group(0) for m in self._re_full.finditer(text)]
        unquoted = [m.group('bare') for m in self._re.finditer(text) if m.groupdict().get('bare') and m.group('bare') in self._suffix_ns and (not (text[m.start() - 1:m.start()] == '`' and text[m.end():m.end() + 1] == '`'))]
        urls = re.findall('https?://[^\\s`\'\\")]+', text)
        return {'ns_refs': ns_refs, 'unquoted_names': unquoted, 'urls': urls}

    def leftover_refs(self, text):
        p = self.text_problems(text)
        return p['ns_refs'] + p['unquoted_names'] + p['urls']
OURS_BOILERPLATE = [('Environment notes: every tool name carries its system prefix.', 'Environment notes: every system is served from its own API host.'), ('Read tool descriptions carefully;', 'Read endpoint descriptions carefully;'), ('Only use the MCP tools.', "Only use these systems' APIs."), ('(use the login tool with these;', '(use the sign-in endpoint with these;')]

def rewrite_notes(cat, text, stats=None):
    for a, b in OURS_BOILERPLATE:
        text = text.replace(a, b)
    text = cat.rewrite(text, stats=stats)
    return re.sub('\\btool (?=`)', 'endpoint ', text)

API_TOOLS = [
 {"type":"function","function":{"name":"api_search","description":"Search this workspace's local endpoint catalog.","parameters":{"type":"object","properties":{"query":{"type":"string"},"top_k":{"type":"integer","minimum":1,"maximum":100}},"required":["query"]}}},
 {"type":"function","function":{"name":"api_fetch","description":"Call a discovered local endpoint; no external HTTP request is made.","parameters":{"type":"object","properties":{"method":{"type":"string"},"url":{"type":"string"},"params":{"type":["object","string","null"]},"body":{"type":["object","string","null"]}},"required":["method","url"]}}},
 {"type":"function","function":{"name":"base64_encode","description":"URL-safe base64 encoding of text.","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}}
]
