"""Render local data viewers for screenshots. These are NOT Langfuse UI captures."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/lab-results'


def page(name, title, source, value):
    text = value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)
    body = f'''<!doctype html><meta charset="utf-8"><title>{escape(title)}</title>
<style>body{{font:17px Arial;background:#f2f6fa;color:#163447;margin:32px}}pre{{font:15px Consolas,monospace;white-space:pre-wrap;background:white;border:1px solid #cad8e3;border-radius:8px;padding:24px;line-height:1.5}}p{{line-height:1.5}}</style>
<h1>{escape(title)}</h1><p>{escape(source)}</p><pre>{escape(text)}</pre>'''
    (OUT/(name+'.html')).write_text(body,encoding='utf-8')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data=json.loads((ROOT/'data.json').read_text(encoding='utf-8'))['datasets']
    for name in ['01-pytest','02-log-validator','03-dashboard-validator','19-lab-log-validator']:
        page(name,name,'Actual command output, saved in data/lab-results/'+name+'.txt',(OUT/(name+'.txt')).read_text(encoding='utf-8'))
    run=data['16-lab-run.json']
    obs=data['17-lab-observations.json']
    request=max((r for r in run['requests'] if r['phase']=='incident'),key=lambda r:r['latency_ms'])
    cid=request['correlation_id']
    spans=sorted([o for o in obs if o['metadata'].get('correlation_id')==cid],key=lambda o:o['startTime'])
    logs=[r for r in data['18-lab-logs.jsonl'] if r.get('correlation_id')==cid]
    source='Local viewer of actual Langfuse API export in data.json. Project: '+run['project']['name']+'. NOT a Langfuse UI screenshot.'
    page('04-structured-log','Structured request / response logs','Source: data.json / datasets / 18-lab-logs.jsonl',logs)
    page('13-incident-log','Incident log: '+cid,'Source: data.json / datasets / 18-lab-logs.jsonl',logs)
    page('12-incident-metric','Latency P95: baseline / incident / recovered','Source: data.json / 16-lab-run.json. Challenge: '+run['challenge_id']+'; latency panel threshold 3000 ms; challenge threshold 2000 ms.',run['phase_metrics'])
    page('06-trace-list','19 traces: root observations',source,[{k:o[k] for k in ['traceId','startTime','latency']} for o in obs if o['name']=='lab-agent-run'])
    table='Trace: '+spans[0]['traceId']+'\nCorrelation ID: '+cid+'\n\n'
    for o in spans:
        table+=f"{o['name']:<20} {o['latency']*1000:>7.1f} ms  {o['level']}\n  ID: {o['id']}   parent: {o['parentObservationId']}\n  {o['startTime']} -> {o['endTime']}\n\n"
    page('07-trace-waterfall','Trace span timing and parent relationships',source,table)
    page('14-incident-trace','Incident trace: retrieval dominates duration',source,table)
    generation=next(o for o in spans if o['name']=='generation')
    page('08-trace-metadata','Generation metadata, prompt, usage and cost',source,{k:generation[k] for k in ['traceId','metadata','promptName','promptVersion','usageDetails','costDetails']})
    page('09-prompt-versions','Prompt versions: creation snapshot before promote',source,{label:{k:p[k] for k in ['name','version','labels','prompt']} for label,p in data['09-prompt-versions.json'].items()})
    stages=[]
    for r in run['requests']:
        if r['phase'].startswith('prompt-'):
            root=next(o for o in obs if o['name']=='lab-agent-run' and o['metadata']['correlation_id']==r['correlation_id'])
            stages.append({'phase':r['phase'],'label':r['prompt_label'],'version':r['prompt_version'],'trace_id':root['traceId']})
    page('10-prompt-rollback','Production: promote v2, rollback v1',source,{'transitions':data['10-prompt-rollback.json'],'traces':stages})


if __name__=='__main__':
    main()
