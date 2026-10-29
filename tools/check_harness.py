#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline check that the public harness refuses interference between cohorts."""
import pathlib
import sys
import tempfile

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'benchmarks'))
import harness as h


class FakeClient:
    def __init__(self):
        self.prompt=0
        self.generated=0
        self.calls=0

    def idle(self,**kwargs):
        return {'tensorfold:prompt_tokens_total':self.prompt,
                'tensorfold:generation_tokens_total':self.generated,
                'tensorfold:requests_running':0,'tensorfold:requests_waiting':0}

    def request(self,body,path):
        self.calls+=1
        self.prompt+=3
        self.generated+=1
        return {'complete':True,'usage':{'prompt_tokens':3,'completion_tokens':1}}


def main():
    with tempfile.TemporaryDirectory() as directory:
        h.ROOT=pathlib.Path(directory)
        h.C=FakeClient()
        h.ARM_LEDGER.clear()
        h.cohort('off','clean',[{'requests':[{}]}],False)
        assert h.C.calls==1
        h.C.prompt+=10
        try:
            h.cohort('off','interference',[{'requests':[{}]}],False)
        except RuntimeError as error:
            assert 'between cohorts' in str(error)
        else:
            raise AssertionError('Interference was not rejected')
        assert h.C.calls==1,'A request was sent after interference'
    print('Offline harness guard passed; no network or inference used.')


if __name__=='__main__':
    main()
