# SPDX-License-Identifier: Apache-2.0
"""Matched empty-cache cold-to-warm cycles; labels never enter the payloads."""
import json,pathlib,sys,time
import harness as h
from make_fixtures import image,prose

def settle(arm,label):
    began=time.monotonic()
    for _ in range(300):
        m=h.C.metrics()
        keys=['tensorfold:spill_writes_pending{rank="0"}','tensorfold:spill_writes_pending{rank="1"}','tensorfold:prompt_cache_restores_active']
        if all(m.get(k)==0 for k in keys):
            (h.ROOT/'results'/arm/(label+'-settled.json')).write_text(json.dumps({'seconds':time.monotonic()-began,'metrics':m},indent=2));return
        time.sleep(.2)
    raise RuntimeError('Cache work did not settle; stop rather than compare unmatched in-flight state')

def features(arm):
    img=h.body('',80);img['messages']=[{'role':'user','content':[{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':'What is the dominant color? Return only its name.'}]}]
    h.cohort(arm,'short-vision',[{'requests':[img]}],False)
    high=h.body('Find the smallest positive integer divisible by all integers 1 to 12. Explain your reasoning.',256);high['reasoning_effort']='high'
    h.cohort(arm,'high',[{'requests':[high]}],False)
    tool=h.body('Use record_code to record the integer 73182.',128)
    tool.update(tools=[{'type':'function','function':{'name':'record_code','description':'Record a code','parameters':{'type':'object','properties':{'code':{'type':'integer'}},'required':['code']}}}],tool_choice={'type':'function','function':{'name':'record_code'}})
    h.cohort(arm,'tool',[{'requests':[tool]}],False)

def suite(arm):
    features(arm)
    if arm=='production':return
    histories=[];chats=[]
    for i in range(8):
        code=str(740041+113*i)
        text=f'Owned I/O study archive {i}.\n'+prose(89900,9372+i)+f'\nThe archive verification code is {code}. Return only that code.'
        content=[{'type':'text','text':f'Owned archive {i}.'},{'type':'image_url','image_url':{'url':image()}},{'type':'text','text':text}]
        base=[{'role':'user','content':content}];histories.append((base,code))
        b=h.body('',16);b['messages']=base;chats.append({'offset_s':.15*i,'requests':[b]})
    cycle=time.monotonic()
    cold=h.cohort(arm,'images-cold-n8',chats,False)
    for row,(_,code) in zip(cold['rows'],histories):
        assert row['content'].strip()==code
        assert row['usage']['prompt_tokens_details']['cached_tokens']==0
    settle(arm,'after-cold')
    warm=[]
    for base,code in histories:
        b=h.body('',16);b['messages']=base+[{'role':'assistant','content':code},{'role':'user','content':'Repeat only the same verification code.'}]
        warm.append({'requests':[b]})
    for rep in range(3):
        d=h.cohort(arm,f'images-warm-n8-r{rep}',warm,False)
        assert all(row['content'].strip()==code for row,(_,code) in zip(d['rows'],histories))
        settle(arm,f'after-warm-{rep}')
    (h.ROOT/'results'/arm/'cycle.json').write_text(json.dumps({'seconds':time.monotonic()-cycle,'initial_cache':'new empty isolated root','warm_state':'result of the same cold workload under this arm; not an identical disk snapshot'},indent=2))
    h.cohort(arm,'cold32k',[{'requests':[h.body('Owned fixed I/O fresh test.\n'+prose(32500,529)+'\nReturn only 72931.',16)]}],False)
    history='Owned fixed I/O mixed test.\n'+prose(89900,6372)+'\nReturn only 730041.'
    prime=h.cohort(arm,'prime90k',[{'requests':[h.body(history,16)]}],False);assert prime['rows'][0]['content'].strip()=='730041';settle(arm,'before-mixed')
    waves=[]
    for wave in range(3):
        b=h.body('',1024);b['messages']=[{'role':'user','content':history},{'role':'assistant','content':'730041'},{'role':'user','content':f'Wave {wave}. '+h.PROSE}];waves.append(b)
    mixed=[{'requests':waves}]
    for i in [1,2]:mixed.append({'offset_s':2*i,'requests':[h.body(f'Owned I/O cold mixed {i}.\n'+prose(32500,62000+i)+'\nReturn only 72931.',16)]})
    h.cohort(arm,'mixed',mixed,False)

if __name__=='__main__':
    args=h.configure(require_seed=False)
    if args.run:suite(args.arm)
