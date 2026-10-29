# SPDX-License-Identifier: Apache-2.0
"""Finite 30-minute owned workload on conditionally adopted configuration."""
import copy,json,time
import harness as h
from suite import body,run,settle,codes,features
from make_fixtures import prose,image

def main():
    begin=time.monotonic();histories=[];rounds=[]
    features('canary')
    for i in range(4):
        code=str(901700+i);text=f'Canary conversation {i}, archive code {code}.\n'+prose(60000,91000+i)+f'\nReturn only {code}.'
        content=text if i%2==0 else [{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':text}]
        histories.append([{'role':'user','content':content}])
    turn=0
    while time.monotonic()-begin<1800 or turn<8:
        # Grow to ~140k, then retain the history without exceeding the context cap.
        bs=[]
        for i,hist in enumerate(histories):
            if turn:hist.append({'role':'user','content':(prose(10000,92000+turn*4+i)+'\n' if turn<=8 else '')+f'Start your reply with the exact archive code introduced in the first message, without formatting. Then write about 500 words explaining retry design for distributed jobs, with a different example for turn {turn}.'})
            b=body('');b['messages']=copy.deepcopy(hist);bs.append(b)
        d=run('canary',f'conversation-{turn}',bs,[.3*i for i in range(4)])
        if turn==0:codes(d,[str(901700+i) for i in range(4)])
        else:
            assert all(str(901700+i) in r['content'][:64] and r['usage']['completion_tokens']>=256 for i,r in enumerate(d['rows']))
        for hist,r in zip(histories,d['rows']):hist.append({'role':'assistant','content':r['content']})
        n=[1,4,8][turn%3]
        bs=[body(f'Canary decode round {turn} stream {i}. Explain distributed task scheduling in about 1200 words with concrete code examples.') for i in range(n)]
        generated=run('canary',f'decode-{turn}-n{n}',bs)
        assert all(r['usage']['completion_tokens']>=512 for r in generated['rows'])
        settle();rounds.append({'turn':turn,'elapsed_s':time.monotonic()-begin,'n':n,'prompt_tokens':[r['usage']['prompt_tokens'] for r in d['rows']],'generated_tokens':[r['usage']['completion_tokens'] for r in generated['rows']]})
        (h.ROOT/'results/canary/progress.json').write_text(json.dumps(rounds,indent=2));turn+=1
    files=sorted((h.ROOT/'results/canary').glob('*-attempt0/result.json'),key=lambda p:p.stat().st_mtime)
    ds=[json.loads(p.read_text()) for p in files]
    expected={k:sum(r['usage'][v] for d in ds for r in d['rows']) for k,v in [('prompt_tokens_total','prompt_tokens'),('generation_tokens_total','completion_tokens')]}
    observed={k:ds[-1]['after']['tensorfold:'+k]-ds[0]['before']['tensorfold:'+k] for k in expected}
    assert expected==observed,'Unowned inference between trial cohorts'
    features_result={'duration_s':time.monotonic()-begin,'rounds':rounds,'complete':True,'whole_arm_accounting':{'expected':expected,'observed':observed},'scope':'finite thirty-minute trial, not full-day proof'}
    (h.ROOT/'results/canary/complete.json').write_text(json.dumps(features_result,indent=2))

if __name__=='__main__':
    args=h.configure(require_seed=False,arm_choices=('canary',))
    if args.run:main()
