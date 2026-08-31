# -*- coding: utf-8 -*-
"""Utilities to talk to the Azure DevOps REST API (devops extension helper).

Shipped with the devops extension; installed at:
.specify/extensions/devops/scripts/python/ado.py

Used by the speckit-devops-* skills. Centralizes:
- org/project detection from remote.origin.url (falls back to defaults)
- az CLI token retrieval (Bearer)
- JSON Patch work item create/update
- ADO field discovery (allowedValues, etc.)
"""
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

# Fallbacks used only when remote detection fails
DEFAULT_ORG = 'https://dev.azure.com/IngeoVisualServicesSAS'
DEFAULT_PROJECT = 'Oryon'
AZ_RESOURCE = '499b84ac-1321-427f-aa17-267ca6975798'

# Valores validados para el picklist 'Value Area' del proceso IngeoVisualServicesSASAgile
ALLOWED_VALUE_AREAS = ['Architecture', 'BackEnd', 'DevOps', 'FrontEnd', 'Infrastructure']

_REMOTE_PATTERNS = (
    # https://dev.azure.com/{org}/{project}/_git/{repo}
    re.compile(r'https://dev\.azure\.com/([^/]+)/([^/]+?)(?:/_git|/?$)'),
    # git@ssh.dev.azure.com:v3/{org}/{project}/{repo}
    re.compile(r'git@ssh\.dev\.azure\.com:v3/([^/]+)/([^/]+)'),
)


def get_org_project():
    """Return (org_url, project) detected from the repo's ADO remote."""
    try:
        git_cmd = shutil.which('git')
        if git_cmd:
            result = subprocess.run(
                [git_cmd, 'config', '--get', 'remote.origin.url'],
                capture_output=True, text=True,
            )
            url = (result.stdout or '').strip()
            for pattern in _REMOTE_PATTERNS:
                m = pattern.match(url)
                if m:
                    return 'https://dev.azure.com/' + m.group(1), m.group(2)
    except OSError:
        pass
    return DEFAULT_ORG, DEFAULT_PROJECT


def get_token() -> str:
    az_cmd = shutil.which('az')
    result = subprocess.run(
        [az_cmd, 'account', 'get-access-token', '--resource', AZ_RESOURCE,
         '--query', 'accessToken', '-o', 'tsv'],
        capture_output=True, text=True, shell=True,
        executable=os.environ.get('COMSPEC'),
    )
    raw = result.stdout.strip()
    if not raw:
        raise RuntimeError('No ADO token: ' + (result.stderr or '')[:200])
    return raw.splitlines()[-1]


def _request(url: str, method: str = 'GET', payload=None, token: str = None):
    token = token or get_token()
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Content-Type', 'application/json-patch+json'
                   if (payload and isinstance(payload, list)) else 'application/json')
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {'message': body[:400]}
        raise RuntimeError(f'HTTP {exc.code}: {detail.get("message", body)[:600]}') from None


def wi_url(wit: str, wid: int = None) -> str:
    org, project = get_org_project()
    base = f'{org}/{project}/_apis/wit/workitems'
    if wid is None:
        return f'{base}/{urllib.parse.quote("%24" + wit, safe="%24")}?api-version=7.1'
    return f'{base}/{wid}?api-version=7.1'


def create_work_item(wit: str, title: str, description: str = '',
                     value_area: str = None, tags: list = None,
                     acceptance_criteria: str = None, priority: int = None) -> dict:
    ops = [{'op': 'add', 'path': '/fields/System.Title', 'value': title}]
    if description:
        ops.append({'op': 'add', 'path': '/fields/System.Description', 'value': description})
    if acceptance_criteria:
        ops.append({'op': 'add', 'path': '/fields/Microsoft.VSTS.Common.AcceptanceCriteria', 'value': acceptance_criteria})
    if value_area:
        if value_area not in ALLOWED_VALUE_AREAS:
            raise ValueError(f'ValueArea {value_area!r} no permitido;Use {ALLOWED_VALUE_AREAS}')
        ops.append({'op': 'add', 'path': '/fields/Microsoft.VSTS.Common.ValueArea', 'value': value_area})
    if tags:
        ops.append({'op': 'add', 'path': '/fields/System.Tags', 'value': ';'.join(tags)})
    if priority:
        ops.append({'op': 'add', 'path': '/fields/Microsoft.VSTS.Common.Priority', 'value': priority})
    return _request(wi_url(wit), method='POST', payload=ops)


def add_parent(wid: int, parent_id: int) -> dict:
    org, project = get_org_project()
    url = org + f'/{project}/_apis/wit/workitems/{wid}?api-version=7.1'
    ops = [{
        'op': 'add', 'path': '/relations/-',
        'value': {
            'rel': 'System.LinkTypes.Hierarchy-Reverse',
            'url': f'{org}/_apis/wit/workItems/{parent_id}',
        },
    }]
    return _request(url, method='PATCH', payload=ops)


def add_comment(wid: int, text: str) -> dict:
    token = get_token()
    org, project = get_org_project()
    url = f'{org}/{project}/_apis/wit/workitems/{wid}/comments?api-version=7.0-preview.3'
    data = json.dumps({'text': text}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def update_fields(wid: int, fields: dict) -> dict:
    org, project = get_org_project()
    ops = [{'op': 'add', 'path': f'/fields/{k}', 'value': v} for k, v in fields.items()]
    return _request(f'{org}/{project}/_apis/wit/workitems/{wid}?api-version=7.1', method='PATCH', payload=ops)


def get_field_allowed_values(wit: str, field_ref: str) -> list:
    org, project = get_org_project()
    url = f'{org}/{project}/_apis/wit/workitemtypes/{wit}/fields/{field_ref}?$expand=allowedValues&api-version=7.1'
    data = _request(url)
    return data.get('allowedValues') or []


def summary(wi: dict) -> str:
    f = wi.get('fields', {})
    return f"#{wi['id']} [{f.get('System.WorkItemType')}] {f.get('System.Title')} | State={f.get('System.State')} | Tags={f.get('System.Tags')}"


# --- CLI ---

if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'rename-feature':
        wid = int(sys.argv[2])
        print(summary(update_fields(wid, {'System.Title': sys.argv[3]})))
    elif cmd == 'create-wi':
        args = json.loads(sys.argv[2])
        wi = create_work_item(args['type'], args['title'], args.get('description', ''),
                              value_area=args.get('value_area'),
                              tags=args.get('tags'),
                              acceptance_criteria=args.get('acceptance_criteria'),
                              priority=args.get('priority'))
        parent = args.get('parent_id')
        if parent:
            add_parent(wi['id'], parent)
            wi['parentId'] = parent
        print(json.dumps({
            'id': wi.get('id'),
            'url': wi.get('url'),
            'fields': {k: wi['fields'].get(k) for k in ('System.Title', 'System.State', 'System.Tags', 'Microsoft.VSTS.Common.ValueArea')},
        }, indent=2))
    elif cmd == 'values':
        print(json.dumps(get_field_allowed_values(sys.argv[2], sys.argv[3]), indent=2))
    else:
        print('Usage: ado.py [rename-feature wid title | create-wi json | values wit fieldref]')


# --- CLI ---

if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'rename-feature':
        wid = int(sys.argv[2])
        print(summary(update_fields(wid, {'System.Title': sys.argv[3]})))
    elif cmd == 'create-wi':
        args = json.loads(sys.argv[2])
        wi = create_work_item(args['type'], args['title'], args.get('description', ''),
                              value_area=args.get('value_area'),
                              tags=args.get('tags'),
                              acceptance_criteria=args.get('acceptance_criteria'),
                              priority=args.get('priority'))
        parent = args.get('parent_id')
        if parent:
            add_parent(wi['id'], parent)
            wi['parentId'] = parent
        print(json.dumps({k: wi.get(k) for k in ('id', 'title', 'url', 'state')} | {
            'fields': {k: wi['fields'].get(k) for k in ('System.Title', 'System.State', 'System.Tags', 'Microsoft.VSTS.Common.ValueArea')},
        }, indent=2))
    elif cmd == 'values':
        print(json.dumps(get_field_allowed_values(sys.argv[2], sys.argv[3]), indent=2))
    else:
        print('Usage: ado.py [rename-feature wid title | create-wi json | values wit fieldref]')