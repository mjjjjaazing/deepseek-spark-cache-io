#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Copy the pinned patched engine, apply the opt-in overlay and run CPU host checks."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=pathlib.Path,required=True)
    p.add_argument('--zig',type=pathlib.Path,required=True)
    p.add_argument('--out',type=pathlib.Path,required=True)
    p.add_argument('--repeat',type=int,default=5)
    a=p.parse_args();a.source=a.source.resolve();a.zig=a.zig.resolve();a.out=a.out.resolve()
    here=pathlib.Path(__file__).resolve().parent.parent
    if subprocess.check_output([str(a.zig),'version'],text=True).strip()!='0.17.0':
        raise SystemExit('Requires Zig 0.17.0')
    if a.repeat<1:raise SystemExit('repeat must be positive')
    for name,want in json.loads((here/'provenance/base-file-hashes.json').read_text()).items():
        if hashlib.sha256((a.source/name).read_bytes()).hexdigest()!=want:
            raise SystemExit('Baseline mismatch: '+name)
    if a.out==a.source or a.source in a.out.parents:
        raise SystemExit('Use an output directory outside the source')
    a.out.mkdir(parents=True,exist_ok=False)
    for arm in ('control','candidate','negative'):
        shutil.copytree(a.source/'zig',a.out/arm/'zig')
    for arm in ('candidate','negative'):
        subprocess.run(['git','apply','--check',str(here/'patches/9999-cache-io-backpressure.patch')],cwd=a.out/arm,check=True)
        subprocess.run(['git','apply',str(here/'patches/9999-cache-io-backpressure.patch')],cwd=a.out/arm,check=True)
    name='zig/src/core/lane_host.zig'
    shutil.copyfile(a.source/name,a.out/'negative'/name)
    env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(a.out/'zig-cache'))
    env.pop('TF_SPILL_IO_BACKPRESSURE',None)
    env.pop('TF_DS_PREFILL_ADMIT_TOKENS',None)
    results=[]
    checks=[('control',None,0),('candidate',None,0)]
    checks += [('negative','io-only: pending restore survives',1)]*a.repeat
    checks += [('candidate','io-only:',0)]*a.repeat
    checks += [('negative','io-only: existing full-tier',0)]
    for index,(arm,phrase,want) in enumerate(checks):
        root=a.out/arm
        cmd=[str(a.zig),'test','-lc','--dep','lanes',f'-Mroot={root}/zig/src/core/engine_api.zig',f'-Mlanes={root}/zig/src/core/lanes/lanes.zig']
        if phrase:cmd+=['--test-filter',phrase]
        proc=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180)
        log=proc.stdout+proc.stderr
        (a.out/f'{index:02d}-{arm}.log').write_text(log)
        verified=proc.returncode==want
        if want:verified &= 'cached=0, committed=0, timeouts=1' in log and '4 passed; 0 skipped; 1 failed.' in log
        else:verified &= 'All ' in log and 'tests passed.' in log
        row=dict(arm=arm,filter=phrase,exit=proc.returncode,expected_exit=want,verified=verified)
        results.append(row);print(json.dumps(row),flush=True)
        (a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        if not verified:raise SystemExit('Unexpected test result; see retained logs')


if __name__=='__main__':main()
