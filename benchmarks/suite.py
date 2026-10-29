# SPDX-License-Identifier: Apache-2.0
"""Owned synthetic extended validation; every request allows 32768 output tokens."""
import copy,json,sys,threading,time,subprocess
import harness as h
from make_fixtures import image,prose

def body(text):return h.body(text,32768)
def run(arm,label,bodies,offsets=None):
    return h.cohort(arm,label,[{'offset_s':(offsets or [0]*len(bodies))[i],'requests':[b]} for i,b in enumerate(bodies)],False)
def settle():
    for _ in range(300):
        m=h.C.metrics()
        if all(m.get(k)==0 for k in ['tensorfold:spill_writes_pending{rank="0"}','tensorfold:spill_writes_pending{rank="1"}','tensorfold:prompt_cache_restores_active']):return
        time.sleep(.2)
    raise RuntimeError('Cache did not settle')
def codes(result,wanted):
    assert [r['content'].strip() for r in result['rows']]==wanted
    assert all(r['finish']=='stop' for r in result['rows'])

def stress(arm):
    # Same frozen candidate cache as the prior reproduction, normal allowance.
    seed=json.loads(h.SEED_REQUEST.read_text())[0]['requests'][0]
    seed['max_tokens']=32768
    barrier=body('Owned normal-limit starvation barrier.\n'+prose(65000,81117)+'\nReturn only 750011.')
    fresh=body('')
    fresh['messages']=[{'role':'user','content':[{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':'Owned normal-limit fresh image.\n'+prose(89900,81118)+'\nReturn only 750071.'}]}]
    observations=[];stop=threading.Event();base=h.C.metrics()['tensorfold:generation_tokens_total']
    def observe():
        for _ in range(60):
            if stop.wait(1):break
            m=h.C.metrics();observations.append({'waiting':m['tensorfold:requests_waiting'],'generated':m['tensorfold:generation_tokens_total']})
            if m['tensorfold:generation_tokens_total']>base:break
    t=threading.Thread(target=observe,daemon=True);t.start()
    try:d=run(arm,'normal-limit-disk-starvation',[barrier,seed,fresh],[0,2,3])
    finally:
        stop.set();t.join(12)
        (h.ROOT/'results'/arm/'stress-queue.json').write_text(json.dumps({'base':base,'observations':observations,'queued':any(x['waiting']>=2 and x['generated']==base for x in observations)},indent=2))
    codes(d,['750011','730041','750071']);settle()

def features(arm):
    b=body('');b['messages']=[{'role':'user','content':[{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':'What is the dominant color? Return only its name.'}]}]
    d=run(arm,'vision',[b]);assert 'blue' in d['rows'][0]['content'].lower()
    b=body('Find the smallest positive integer divisible by all integers 1 to 12. Explain briefly.');b['reasoning_effort']='high'
    d=run(arm,'reasoning',[b]);assert '27720' in d['rows'][0]['content'].replace(',','')
    b=body('Use record_code to record the integer 73182.')
    b.update(tools=[{'type':'function','function':{'name':'record_code','description':'Record a code','parameters':{'type':'object','properties':{'code':{'type':'integer'}},'required':['code']}}}],tool_choice={'type':'function','function':{'name':'record_code'}})
    d=run(arm,'tool',[b]);r=d['rows'][0];assert r['finish']=='tool_calls'
    args=''.join(x.get('function',{}).get('arguments','') for x in r['tool_deltas']);assert json.loads(args)['code']==73182

def growing(arm):
    histories=[]
    for i in range(4):
        code=str(861100+i)
        text=f'Owned growing conversation {i}. Archive code {code}.\n'+prose(50000,82200+i)+f'\nReturn only archive code {code}.'
        content=text if i%2==0 else [{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':text}]
        histories.append([{'role':'user','content':content}])
    for turn in range(5):
        bodies=[]
        for i,hist in enumerate(histories):
            if turn:
                # Append both actual assistant replies and fresh context; no fake history.
                hist.append({'role':'user','content':f'Owned extension {turn}.\n'+prose(14000,83000+turn*10+i)+f'\nReturn only the original archive code {861100+i}.'})
            b=body('');b['messages']=copy.deepcopy(hist);bodies.append(b)
        d=run(arm,f'growing-four-turn-{turn}',bodies)
        codes(d,[str(861100+i) for i in range(4)])
        for hist,r in zip(histories,d['rows']):hist.append({'role':'assistant','content':r['content']})
        settle()
    (h.ROOT/'results'/arm/'growing-history-summary.json').write_text(json.dumps({'turns':5,'conversations':4,'final_prompt_tokens':[r['usage']['prompt_tokens'] for r in d['rows']]},indent=2))

def eight(arm):
    histories=[]
    for i in range(8):
        code=str(872100+i)
        text=f'Owned full allowance eight-way history {i}.\n'+prose(89900,84000+i)+f'\nReturn only {code}.'
        histories.append([{'role':'user','content':[{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':text}]}])
    for turn in range(4):
        bs=[]
        for hist in histories:
            if turn:hist.append({'role':'user','content':'Repeat only the original verification code.'})
            b=body('');b['messages']=copy.deepcopy(hist);bs.append(b)
        d=run(arm,f'eight-image-turn-{turn}',bs,[.15*i for i in range(8)] if turn==0 else None)
        codes(d,[str(872100+i) for i in range(8)])
        for hist,r in zip(histories,d['rows']):hist.append({'role':'assistant','content':r['content']})
        settle()

def generation(arm):
    # A real sustained output, not a three-token retrieval with a large allowance.
    prompt='Write an extensive engineering handbook of at least 8000 words about TCP, congestion control, HTTP connection pooling, retries, streaming and observability. Use 20 numbered sections, detailed examples and substantial code. Do not summarize or stop early.'
    d=run(arm,'long-generation',[body(prompt)])
    assert d['rows'][0]['usage']['completion_tokens']>=4096,'Long generation coverage insufficient'
    for n in [1,4,8]:
        bs=[body(f'Owned concurrent generation stream {i}. Write about 1000 words explaining TCP reliability and timeout design, with detailed examples.') for i in range(n)]
        d=run(arm,f'generate-n{n}',bs)
        assert all(r['usage']['completion_tokens']>=512 for r in d['rows']),'Concurrent decode too short'
    bs=[body('Owned mixed continuous decode. Write at least 4000 words on reliable distributed job queues with implementation examples.')]
    for i in range(1,4):
        b=body(f'Owned fresh mixed text {i}.\n'+prose(32000,85000+i)+f'\nReturn only {883100+i}.')
        if i==3:b['messages'][0]['content']=[{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':b['messages'][0]['content']}]
        bs.append(b)
    d=run(arm,'mixed-long-generation',bs,[0,2,4,6]);assert d['rows'][0]['usage']['completion_tokens']>=2048
    assert [r['content'].strip() for r in d['rows'][1:]]==[str(883100+i) for i in range(1,4)]

def suite(arm):
    stress(arm);features(arm);growing(arm);eight(arm);generation(arm)
    for rep in range(3):
        bs=[body(f'Owned final repeated concurrency {i}. Explain HTTP retry safety in about 500 words with examples.') for i in range(4)]
        run(arm,f'repeated-n4-{rep}',bs)
    settle()
    (h.ROOT/'results'/arm/'extended-complete.json').write_text(json.dumps({'complete':True,'all_max_tokens':32768,'service_time':time.time()}))

if __name__=='__main__':
    args=h.configure()
    if args.run:suite(args.arm)
