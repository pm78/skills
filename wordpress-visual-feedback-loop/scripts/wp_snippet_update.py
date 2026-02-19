#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
from urllib import request


def auth_header() -> str:
    user = os.getenv('WP_TTT_APP_USERNAME')
    pwd = os.getenv('WP_TTT_APP_PASSWORD')
    if not user or not pwd:
        raise RuntimeError('Missing WP_TTT_APP_USERNAME or WP_TTT_APP_PASSWORD')
    token = base64.b64encode(f'{user}:{pwd}'.encode()).decode()
    return f'Basic {token}'


def http_json(url: str, method='GET', data=None):
    headers = {'Authorization': auth_header()}
    raw = None
    if data is not None:
        raw = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = request.Request(url, data=raw, method=method, headers=headers)
    with request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode('utf-8'))


def main():
    ap = argparse.ArgumentParser(description='Update one Code Snippets entry via WP REST.')
    ap.add_argument('--site', required=True, help='Example: https://thrivethroughtime.com')
    ap.add_argument('--snippet-id', required=True, type=int)
    ap.add_argument('--code-file', required=True)
    args = ap.parse_args()

    site = args.site.rstrip('/')
    endpoint = f'{site}/wp-json/code-snippets/v1/snippets/{args.snippet_id}'

    with open(args.code_file, 'r', encoding='utf-8') as f:
      new_code = f.read()

    current = http_json(endpoint)
    payload = {
        'name': current.get('name', f'Snippet {args.snippet_id}'),
        'desc': current.get('desc', ''),
        'code': new_code,
        'tags': current.get('tags', []),
        'scope': current.get('scope', 'front-end'),
        'condition_id': current.get('condition_id', 0),
        'active': current.get('active', True),
        'priority': current.get('priority', 10),
    }

    updated = http_json(endpoint, method='PUT', data=payload)
    print(json.dumps({
        'id': updated.get('id'),
        'name': updated.get('name'),
        'active': updated.get('active'),
        'modified': updated.get('modified'),
        'code_error': updated.get('code_error'),
    }, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
