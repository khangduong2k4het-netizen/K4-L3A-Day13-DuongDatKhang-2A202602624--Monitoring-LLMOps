"""Run the lab in an isolated process; writes prompts/traces to configured Langfuse.

Usage: python scripts/complete_lab.py --run (explicit remote writes)
       python scripts/complete_lab.py --collect (read observations for last run)
Existing API logs and incident state are preserved.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / 'data/lab-results'
DATA = ROOT / 'data.json'


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def save(name, value):
    bundle = json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else {'schema_version': 1, 'datasets': {}}
    bundle['datasets'][name] = value
    DATA.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--run', action='store_true')
    action.add_argument('--collect', action='store_true')
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    import httpx
    base = os.environ['LANGFUSE_BASE_URL'].rstrip('/')
    if base != 'https://us.cloud.langfuse.com':
        raise RuntimeError('This lab run is authorized for https://us.cloud.langfuse.com only')
    api = httpx.Client(base_url=base, auth=(os.environ['LANGFUSE_PUBLIC_KEY'], os.environ['LANGFUSE_SECRET_KEY']), timeout=30)
    if args.collect:
        manifest = json.loads(DATA.read_text(encoding='utf-8'))['datasets']['16-lab-run.json']
        params = dict(fromStartTime=manifest['start'], toStartTime=manifest['end'], fields='core,basic,metadata,usage,prompt', limit=100)
        observations = []
        while True:
            result = api.get('/api/public/v2/observations', params=params)
            result.raise_for_status()
            page = result.json()
            for obs in page['data']:
                metadata = obs.get('metadata') or {}
                obs['metadata'] = {k:v for k,v in metadata.items() if not k.startswith(('scope.', 'resourceAttributes.'))}
                observations.append(obs)
            cursor = page.get('meta', {}).get('cursor')
            if not cursor:
                break
            params['cursor'] = cursor
        ids = {r['correlation_id'] for r in manifest['requests']}
        observations = [o for o in observations if o.get('metadata', {}).get('correlation_id') in ids]
        save('17-lab-observations.json', observations)
        print(f'Collected {len(observations)} observations / {len({o["traceId"] for o in observations})} traces')
        return

    projects = api.get('/api/public/projects')
    projects.raise_for_status()
    manifest = dict(start=now(), project=projects.json()['data'][0], requests=[], transitions=[])
    run_dir = ROOT / 'data/log-runs' / datetime.now(timezone.utc).strftime('complete-%Y%m%d-%H%M%S')
    run_dir.mkdir(parents=True)
    os.environ['LOG_PATH'] = str(run_dir / 'logs.jsonl')
    os.environ['LANGFUSE_PROMPT_NAME'] = 'day13-chat'
    from langfuse import get_client
    from fastapi.testclient import TestClient
    from app.main import app
    from app.challenge import load_challenge, ordered_queries
    from app.metrics import percentile
    from scripts import validate_logs
    lf = get_client()
    template = 'Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}'
    versions = {}
    for label, text in [('baseline', template), ('candidate', template + '\nAnswer concisely in three bullet points.')]:
        lookup = api.get('/api/public/v2/prompts/day13-chat', params={'label':label})
        if lookup.status_code == 404:
            p = lf.create_prompt(name='day13-chat', type='text', prompt=text, labels=[label], commit_message='Day13 observability lab ' + label)
            versions[label] = p.version
        else:
            lookup.raise_for_status()
            versions[label] = lookup.json()['version']
    save('09-prompt-versions.json', {label:api.get('/api/public/v2/prompts/day13-chat',params={'version':v}).json() for label,v in versions.items()})

    def transition(label):
        lf.update_prompt(name='day13-chat', version=versions[label], new_labels=['production'])
        p = lf.get_prompt('day13-chat',label='production',cache_ttl_seconds=0)
        assert p.version == versions[label]
        manifest['transitions'].append(dict(at=now(), production_version=p.version))

    challenge = load_challenge()
    manifest['challenge_id'] = challenge.challenge_id
    query = ordered_queries(challenge)[0]
    with TestClient(app) as client:
        def send(payload, phase, label='production'):
            os.environ['LANGFUSE_PROMPT_LABEL'] = label
            p = lf.get_prompt('day13-chat', label=label, cache_ttl_seconds=0)
            assert not p.is_fallback
            started = now()
            response = client.post('/chat', json=payload)
            response.raise_for_status()
            data = response.json()
            assert response.headers['x-request-id'] == data['correlation_id']
            manifest['requests'].append(dict(phase=phase, start=started, end=now(), correlation_id=data['correlation_id'], latency_ms=data['latency_ms'], ttft_ms=data['ttft_ms'], prompt_label=label, prompt_version=p.version))

        send(query, 'prompt-baseline', 'baseline')
        send(query, 'prompt-candidate', 'candidate')
        transition('candidate')
        try:
            send(query, 'prompt-promoted')
        finally:
            transition('baseline')
        send(query, 'prompt-rollback')
        for payload in ordered_queries(challenge):
            send(payload, 'baseline')
        client.post(f'/incidents/{challenge.incident}/enable').raise_for_status()
        try:
            for payload in ordered_queries(challenge):
                send(payload, 'incident')
        finally:
            client.post(f'/incidents/{challenge.incident}/disable').raise_for_status()
        for payload in ordered_queries(challenge):
            send(payload, 'recovered')
    lf.flush()
    manifest['end'] = now()
    manifest['log_path'] = str(run_dir.relative_to(ROOT) / 'logs.jsonl')
    manifest['phase_metrics'] = {}
    for phase in ['baseline', 'incident', 'recovered']:
        records = [r for r in manifest['requests'] if r['phase']==phase]
        manifest['phase_metrics'][phase] = dict(start=records[0]['start'],end=records[-1]['end'], count=len(records), p95_ms=percentile([r['latency_ms'] for r in records],95),ttft_p95_ms=percentile([r['ttft_ms'] for r in records],95))
    save('16-lab-run.json',manifest)
    save('10-prompt-rollback.json',manifest['transitions'])
    save('18-lab-logs.jsonl', [json.loads(line) for line in (run_dir/'logs.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()])
    validate_logs.LOG_PATH = run_dir/'logs.jsonl'
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        validate_logs.main()
    (EVIDENCE/'19-lab-log-validator.txt').write_text(output.getvalue(),encoding='utf-8')
    print(json.dumps(manifest['phase_metrics']))
    print(output.getvalue())
    lf.shutdown()


if __name__ == '__main__':
    main()
