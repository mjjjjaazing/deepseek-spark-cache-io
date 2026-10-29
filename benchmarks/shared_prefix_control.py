#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Two synthetic exact-output controls; --run contacts an already prepared loopback server."""
import hashlib
import json
import harness as h
from client import closure
from make_fixtures import prose


def payloads():
    for code in ['REF73182', 'REF84479']:
        system = 'Exact shared-checkpoint test.\n'+prose(23000, 91071)+'\nThe reference is '+code+'.\n'+prose(10000, 91072)
        yield code, dict(model='DeepSeek-V4.1-Flash-1017',
                         messages=[dict(role='system', content=system), dict(role='user', content='Begin your answer with the reference from the system message, then explain TCP reliability with concrete examples.')],
                         temperature=0, seed=1234, max_tokens=512, reasoning_effort='none',
                         stream=True, stream_options={'include_usage': True}, return_token_ids=True)


def main():
    args = h.configure(require_seed=False, arm_choices=('control', 'candidate'))
    if not args.run:
        return
    if args.arm == 'candidate' and (h.REFERENCE is None or not (h.REFERENCE/'complete.json').is_file()):
        raise SystemExit('Candidate requires --reference pointing to a completed control output directory')
    if args.arm == 'candidate':
        reference = json.loads((h.REFERENCE/'complete.json').read_text())
        if not reference.get('passed') or reference.get('arm') != 'control':
            raise SystemExit('Reference must be a passed control arm')
    previous = None
    for case, (code, body) in enumerate(payloads()):
        before = h.C.idle()
        if previous is not None:
            for name in ['prompt_tokens_total', 'generation_tokens_total']:
                if before['tensorfold:'+name] != previous['tensorfold:'+name]:
                    raise RuntimeError('Inference or counter reset between owned cases; no next request sent')
        row = h.C.request(body, h.ROOT/f'{case}.sse')
        after = h.C.idle()
        account = closure(before, after, [row])
        if not account['clean'] or not row['complete']:
            raise RuntimeError('Incomplete or unrelated inference; exclude this run')
        ids = row['runtime'][-1].get('token_ids')
        if not ids or code not in row['content'][:100]:
            raise RuntimeError('Missing full token IDs or incorrect reference')
        cached = row['usage']['prompt_tokens_details']['cached_tokens']
        if args.arm == 'control' and cached != 0:
            raise RuntimeError('Control was already cached; prepare a separate empty cache, do not clear a live cache')
        if args.arm == 'candidate':
            old = json.loads((h.REFERENCE/f'{case}-result.json').read_text())
            if row['payload_sha256'] != old['row']['payload_sha256'] or ids != old['row']['runtime'][-1]['token_ids'] or row['content_sha256'] != old['row']['content_sha256']:
                raise RuntimeError('Exact paired output or request mismatch')
            if case == 1 and cached != 22528:
                raise RuntimeError('Expected checkpoint was not exercised')
        result = dict(case=case, row=row, accounting=account,
                      full_token_ids_sha256=hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest())
        (h.ROOT/f'{case}-result.json').write_text(json.dumps(result, indent=2)+'\n')
        previous = after
        print(json.dumps(dict(case=case, cached_tokens=cached, ttft_s=row['ttft_s'], passed=True)), flush=True)
    (h.ROOT/'complete.json').write_text(json.dumps(dict(arm=args.arm, passed=True, cases=2, exact_token_ids_checked=args.arm == 'candidate'))+'\n')


if __name__ == '__main__':
    main()
