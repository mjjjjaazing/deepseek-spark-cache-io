# SPDX-License-Identifier: Apache-2.0
"""Focused production-vs-candidate confirmation with explicitly ordered sends."""
import concurrent.futures,copy,json,pathlib,sys,time
import harness as h
from client import closure,digest,encoded
from suite import body,settle
from make_fixtures import image,prose

def main(arm):
    assert arm in ['off','on'];dest=h.ROOT/'results'/('fairness-v2-'+arm);dest.mkdir(exist_ok=False)
    histories=[];cases=[]
    for i in range(4):
        text=f'Owned staggered fairness confirmation v2 stream {i}.\n'+prose(50000,98100+i)+f'\nReturn only {902600+i}.'
        content=text if i%2==0 else [{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':text}]
        histories.append([{'role':'user','content':content}])
    for turn in range(5):
        bs=[]
        for i,hist in enumerate(histories):
            if turn:hist.append({'role':'user','content':f'Extension {turn}.\n'+prose(14000,98200+turn*10+i)+f'\nReturn only the original code {902600+i}.'})
            b=body('');b['messages']=copy.deepcopy(hist);bs.append(b)
        out=dest/f'turn-{turn}';out.mkdir();(out/'payloads.json').write_text(json.dumps(bs))
        before=h.C.idle();health=h.machine_state();start=time.monotonic()
        def worker(i):
            time.sleep(max(0,start+.3*i-time.monotonic()));sent=time.monotonic()-start
            row=h.C.request(bs[i],out/f'{i}.sse');row.update(chat=i,send_offset_s=sent);return row
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:rows=list(ex.map(worker,range(4)))
        wall=time.monotonic()-start;after=h.C.idle();account=closure(before,after,rows)
        result={'turn':turn,'arm':arm,'before':before,'after':after,'rows':rows,'wall_s':wall,'accounting':account,'health_before':health,'health_after':h.machine_state(),'payload_sha':digest(encoded(bs))}
        (out/'result.json').write_text(json.dumps(result,indent=2))
        assert account['clean'];assert [r['content'].strip() for r in rows]==[str(902600+i) for i in range(4)]
        assert all(rows[i+1]['send_offset_s']-rows[i]['send_offset_s']>=.2 for i in range(3)),'Send order not sufficiently separated'
        if turn==0:assert all(r['usage']['prompt_tokens_details']['cached_tokens']==0 for r in rows),'Initial context unexpectedly warm'
        for hist,r in zip(histories,rows):hist.append({'role':'assistant','content':r['content']})
        settle();cases.append(result)
        print(json.dumps({'arm':arm,'turn':turn,'wall_s':wall,'ttft_s':[r['ttft_s'] for r in rows],'clean':True}),flush=True)
    failures=[]
    if arm=='on':
        for turn,now in enumerate(cases):
            old=json.loads((h.REFERENCE/f'turn-{turn}/result.json').read_text())
            assert old['payload_sha']==now['payload_sha']
            assert [r['runtime'][-1]['token_sha'] for r in old['rows']]==[r['runtime'][-1]['token_sha'] for r in now['rows']]
            if now['wall_s']-old['wall_s']>max(1,.1*old['wall_s']):failures.append(f'turn{turn} batch regression')
            for i,(a,b) in enumerate(zip(old['rows'],now['rows'])):
                for metric,floor in [('ttft_s',1),('elapsed_s',2)]:
                    if b[metric]-a[metric]>max(floor,.1*a[metric]):failures.append(f'turn{turn} request{i} {metric} regression')
    expected={k:sum(r['usage'][v] for d in cases for r in d['rows']) for k,v in [('prompt_tokens_total','prompt_tokens'),('generation_tokens_total','completion_tokens')]}
    observed={k:cases[-1]['after']['tensorfold:'+k]-cases[0]['before']['tensorfold:'+k] for k in expected}
    assert expected==observed,'Unowned inference between cases'
    result={'complete':True,'passed':not failures,'failures':failures,'requests':20,'whole_arm_accounting':{'expected':expected,'observed':observed},'comparison':'original production image0b versus candidate5f enabled; new cold prefixes, same growing payloads, 0.3s send separation'}
    (dest/'complete.json').write_text(json.dumps(result,indent=2));assert not failures,failures

if __name__=='__main__':
    args=h.configure(require_seed=False)
    if args.run:
        if args.arm=='on' and h.REFERENCE is None:raise SystemExit('--reference must name the off-arm fairness-v2-off directory')
        main(args.arm)
