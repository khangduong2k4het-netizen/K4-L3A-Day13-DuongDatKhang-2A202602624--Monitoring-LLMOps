"""Serve the six-panel log dashboard, or export an HTML snapshot.

python scripts/dashboard.py --log data/logs.jsonl --port 8501
python scripts/dashboard.py --log data.json --output data/lab-results/11-dashboard.html
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.metrics import percentile
from scripts.validate_dashboard import load_dashboard_config


def parse_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def read_rows(log_path):
    text = log_path.read_text(encoding='utf-8')
    if log_path.suffix == '.json':
        return json.loads(text)['datasets']['18-lab-logs.jsonl']
    return [json.loads(s) for s in text.splitlines() if s.strip()]


def summarize(rows):
    received = [r for r in rows if r.get('event') == 'request_received']
    responses = [r for r in rows if r.get('event') == 'response_sent']
    failed = [r for r in rows if r.get('event') == 'request_failed']
    tools = [r for r in rows if isinstance(r.get('tool_success'), bool)]
    traffic, costs = Counter(), defaultdict(float)
    for r in received:
        traffic[r['ts'][:16]+'Z'] += 1
    for r in responses:
        costs[r['ts'][:16]+'Z'] += r.get('cost_usd', 0)
    latencies = [r['latency_ms'] for r in responses]
    return {
        'latency': {**{f'P{p}':percentile(latencies,p) for p in (50,95,99)}, 'TTFT P95':percentile([r['ttft_ms'] for r in responses],95)},
        'traffic': dict(traffic),
        'errors': {'error rate':100*len(failed)/len(received) if received else None, 'retrieval success':100*sum(r['tool_success'] for r in tools)/len(tools) if tools else None},
        'cost':dict(costs),
        'tokens': {k:sum(r.get(k,0) for r in responses) for k in ['tokens_in','tokens_out']},
        'quality':{'mean':mean(r['quality_score'] for r in responses) if responses else None},
        'requests':len(received), 'cost_total':sum(costs.values()),
        'error_breakdown':dict(Counter(r.get('error_type','unknown') for r in failed)),
    }


def chart(values, threshold):
    values = values or {'no data':None}
    ceiling = max([float(v) for v in values.values() if v is not None] + [float(threshold), 0.001]) * 1.15
    width = 600
    height = max(120, len(values)*35 + 25)
    line = 150 + 400 * threshold / ceiling
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Values and threshold"><line x1="{line}" x2="{line}" y1="0" y2="{height}" stroke="#c63737" stroke-dasharray="5 4"/>']
    for i,(label,value) in enumerate(values.items()):
        y = 25 + i*35
        parts.append(f'<text x="0" y="{y}" font-size="12">{escape(label)}</text>')
        if value is not None:
            w = 400*value/ceiling
            parts.append(f'<rect x="150" y="{y-15}" width="{w}" height="20" fill="#237a91"/><text x="{155+w}" y="{y}" font-size="12">{value:.4g}</text>')
        else:
            parts.append(f'<text x="150" y="{y}" font-size="12">N/A</text>')
    return ''.join(parts)+'</svg>'


def render(log_path, end=None, refresh=False):
    config = load_dashboard_config(ROOT/'config/dashboard.yaml')['dashboard']
    rows = read_rows(log_path)
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(minutes=config['time_range_minutes'])
    rows = [r for r in rows if start <= parse_time(r['ts']) <= end]
    data = summarize(rows)
    cards=[]
    for panel in config['panels']:
        threshold=panel['threshold']
        note=''
        if panel['id']=='traffic':
            note=f'Total: {data["requests"]}; average over 60m: {data["requests"]/60:.3f} requests/min. Empty minutes count as zero.'
        if panel['id']=='cost':
            note=f'Total in window: ${data["cost_total"]:.6f}. Threshold applies to total, not each minute.'
        if panel['id']=='errors':
            note=f'Error threshold applies only to error rate; retrieval success guardrail: 90%. Breakdown: {data["error_breakdown"]}'
        cards.append(f'<section><h2>{escape(panel["title"])}</h2><p>{escape(panel["unit"])} · {escape(threshold["aggregation"])} {threshold["operator"]} {threshold["value"]} (red line)</p>{chart(data[panel["id"]],threshold["value"])}<p>{escape(note)}</p></section>')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Day13 monitoring dashboard</title>{'<meta http-equiv="refresh" content="30">' if refresh else ''}
<style>body{{font:16px Arial;margin:28px;background:#f1f5f8;color:#153044}}h1{{margin-bottom:8px}}main{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}section{{background:white;border:1px solid #cddbe3;border-radius:10px;padding:18px}}h2{{font-size:20px;margin:0}}p{{font-size:13px}}svg{{width:100%;max-height:220px}}footer{{margin-top:18px}}</style>
<h1>{escape(config['title'])}</h1><p>UTC: {start.isoformat()} → {end.isoformat()} · Window 60m · {'Live refresh 30s' if refresh else 'Exported snapshot; no auto-refresh'}</p><p>Source: {escape(str(log_path))} · {len(rows)} events · Mock LLM workload</p><main>{''.join(cards)}</main><footer>Latency measures agent execution; TTFT measures mock generation only. Success and quality do not prove answer correctness.</footer></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log',type=Path,default=ROOT/'data/logs.jsonl')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--end',help='ISO UTC end, defaults to last log timestamp for export and now for server')
    parser.add_argument('--port',type=int,default=8501)
    args=parser.parse_args()
    end=parse_time(args.end) if args.end else None
    if args.output:
        if end is None:
            end=max(parse_time(row['ts']) for row in read_rows(args.log))
        args.output.write_text(render(args.log,end),encoding='utf-8')
        print(args.output)
        return
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                body=render(args.log,end,refresh=True).encode('utf-8')
            except (OSError,ValueError,KeyError) as exc:
                self.send_error(503, type(exc).__name__)
                return
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
    print(f'Dashboard: http://127.0.0.1:{args.port}',flush=True)
    HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':
    main()
