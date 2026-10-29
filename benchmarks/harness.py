# SPDX-License-Identifier: Apache-2.0
import argparse,concurrent.futures,json,pathlib,time
from client import Client,closure,encoded,digest
ROOT=None
C=None
SEED_REQUEST=None
ARM_LEDGER={}

def configure(require_seed=True, arm_choices=('off','on')):
    global ROOT,C,SEED_REQUEST,REFERENCE
    p=argparse.ArgumentParser(description="Run owned synthetic workloads on an already prepared local server; no deployment or restarts.")
    p.add_argument('arm',choices=arm_choices)
    p.add_argument('--out',type=pathlib.Path,required=True)
    p.add_argument('--seed-request',type=pathlib.Path,required=require_seed)
    p.add_argument('--key-file',type=pathlib.Path)
    p.add_argument('--run',action='store_true')
    p.add_argument('--reference',type=pathlib.Path)
    args=p.parse_args()
    REFERENCE=args.reference.resolve() if args.reference else None
    if not args.run:
        print('Dry run: no inference sent. Read docs/benchmarking.md before using --run.')
        return args
    if not args.key_file:p.error('--run requires --key-file')
    ROOT=args.out.resolve();SEED_REQUEST=args.seed_request.resolve() if args.seed_request else None
    if ROOT.exists():p.error('--out must be a new directory')
    if require_seed and not SEED_REQUEST.is_file():p.error('Seed request file is missing')
    key=args.key_file.read_text().strip()
    if not key:p.error('Key file is empty')
    ROOT.mkdir(parents=True,mode=0o700);(ROOT/'results'/args.arm).mkdir(parents=True)
    C=Client('http://127.0.0.1:8888',key)
    return args

def body(prompt,limit=256,temp=0):
    return dict(model='DeepSeek-V4.1-Flash-1017',messages=[{'role':'user','content':prompt}],max_tokens=limit,temperature=temp,top_p=.95,top_k=20,seed=1234,reasoning_effort='none',stream=True,stream_options={'include_usage':True})

PROSE='Write a detailed technical chapter of at least 2000 words explaining TCP congestion control, reliability, sockets and HTTP. Use full paragraphs and examples.'
CODE='Write a complete Python implementation of an HTTP client with connection pooling, retries, timeouts, streaming responses, comments and unit tests. Explain the design after the code. Be thorough.'

def cohort(arm,label,chats,retry=True):
    for attempt in range(3 if retry else 1):
        out=ROOT/'results'/arm/(label+f'-attempt{attempt}');out.mkdir(parents=True,exist_ok=False)
        before=C.idle(stable=1)
        previous=ARM_LEDGER.get(arm)
        if previous is not None and any(before['tensorfold:'+name]!=previous['tensorfold:'+name] for name in ['prompt_tokens_total','generation_tokens_total']):
            (out/'excluded-reason.json').write_text(json.dumps({'reason':'Inference or counter reset between cohorts; no requests sent for this case.'}))
            raise RuntimeError('Unrelated inference or restart between cohorts; stopped before sending the next case')
        start=time.monotonic()
        def run(i,chat):
            time.sleep(max(0,start+chat.get('offset_s',0)-time.monotonic()));rows=[]
            for j,b in enumerate(chat['requests']):
                row=C.request(b,out/f'{i}-{j}.sse');row.update(chat=i,wave=j);rows.append(row)
                if not row['complete']:break
            return rows
        (out/'payloads.json').write_text(json.dumps(chats,indent=2))
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(chats)) as ex:
            futures=[ex.submit(run,i,ch) for i,ch in enumerate(chats)]
            rows=[r for f in futures for r in f.result()]
        wall=time.monotonic()-start
        after=C.idle(stable=1);account=closure(before,after,rows)
        account['clean']=account['clean'] and len(rows)==sum(len(ch['requests']) for ch in chats)
        valid_timing=account['clean']
        result=dict(label=label,arm=arm,wall_s=wall,before=before,after=after,rows=rows,accounting=account,valid_timing=valid_timing,payload_sha=digest(encoded(chats)))
        (out/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({'arm':arm,'case':label,'clean':account['clean'],'valid_timing':valid_timing,'wall_s':wall}),flush=True)
        if not account['clean']:raise RuntimeError('Incomplete or unrelated inference; retained and stopped')
        ARM_LEDGER[arm]=after
        if valid_timing:return result
    return result

def machine_state():
    # Host inventory is intentionally omitted; record hardware separately without secrets.
    return []
