#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run an already-reviewed synthetic workload on a manually prepared local engine.

No deployment, SSH, cache clearing, restart, or configuration changes. A manifest
contains at most eight chats, each with an offset_s and a list of exact request
bodies. Each chat's requests are sequential. The runner saves raw SSE receipts.
"""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import time
import urllib.request


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def closure(before, after, rows):
    names = ('prompt_tokens_total', 'generation_tokens_total')
    expected = (sum((r.get('usage') or {}).get('prompt_tokens', 0) for r in rows),
                sum((r.get('usage') or {}).get('completion_tokens', 0) for r in rows))
    delta = {n: after['tensorfold:'+n] - before['tensorfold:'+n] for n in names}
    clean = (all(r.get('complete') and r.get('usage') for r in rows)
             and all(delta[n] == v for n, v in zip(names, expected))
             and after['tensorfold:requests_running'] == 0
             and after['tensorfold:requests_waiting'] == 0)
    return {'clean': clean, 'expected': dict(zip(names, expected)), 'delta': delta}


class Client:
    def __init__(self, base, key):
        self.base, self.key = base, key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def open(self, route, data=None):
        request = urllib.request.Request(self.base+route, data=data, headers={
            'Authorization': 'Bearer '+self.key, 'Content-Type': 'application/json'})
        return self.opener.open(request, timeout=1200 if data else 10)

    def metrics(self):
        with self.open('/metrics') as response:
            lines = response.read().decode().splitlines()
        result = {line.split()[0]: float(line.split()[1]) for line in lines
                  if line and not line.startswith('#')}
        for name in ('requests_running', 'requests_waiting', 'prompt_tokens_total', 'generation_tokens_total'):
            if 'tensorfold:'+name not in result:
                raise RuntimeError('Required counter absent: '+name)
        return result

    def idle(self, timeout=60, stable=5):
        deadline, since, previous = time.monotonic()+timeout, None, None
        while time.monotonic() < deadline:
            m = self.metrics()
            counters = (m['tensorfold:prompt_tokens_total'], m['tensorfold:generation_tokens_total'])
            if m['tensorfold:requests_running'] == m['tensorfold:requests_waiting'] == 0:
                if counters != previous or since is None:
                    since = time.monotonic()
                if time.monotonic()-since >= stable:
                    return m
            else:
                since = None
            previous = counters
            time.sleep(.25)
        raise RuntimeError('No five-second idle window; nothing interrupted')

    def request(self, body, path):
        wire = encoded(body)
        row = {'payload_sha256': digest(wire), 'complete': False}
        start, first, finish, usage = time.monotonic(), None, None, None
        text, reasoning, tool_deltas, runtime = [], [], [], []
        try:
            with path.open('wb') as log, self.open('/v1/chat/completions', wire) as response:
                for raw in response:
                    log.write(raw)
                    if not raw.startswith(b'data:'):
                        continue
                    data = raw[5:].strip()
                    if data == b'[DONE]':
                        row['complete'] = True
                        break
                    event = json.loads(data)
                    usage = event.get('usage') or usage
                    if event.get('error'):
                        raise RuntimeError(str(event['error']))
                    if event.get('tensorfold'):
                        runtime.append(event['tensorfold'])
                    for choice in event.get('choices', []):
                        delta = choice.get('delta') or {}
                        content = delta.get('content') or ''
                        thought = delta.get('reasoning_content') or delta.get('reasoning') or ''
                        calls = delta.get('tool_calls') or []
                        if (content or thought or calls) and first is None:
                            first = time.monotonic()
                        text.append(content)
                        reasoning.append(thought)
                        tool_deltas.extend(calls)
                        finish = choice.get('finish_reason') or finish
        except Exception as exc:
            row['error'] = type(exc).__name__+': '+str(exc)
            row['complete'] = False
        row.update(elapsed_s=time.monotonic()-start, ttft_s=None if first is None else first-start,
                   usage=usage, finish=finish, runtime=runtime,
                   content=''.join(text), reasoning_sha256=digest(''.join(reasoning).encode()),
                   content_sha256=digest(''.join(text).encode()), tool_deltas=tool_deltas)
        row['complete'] = bool(row['complete'] and usage and finish)
        return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--key-file', type=pathlib.Path)
    parser.add_argument('--base', default='http://127.0.0.1:8888')
    parser.add_argument('--run', action='store_true', help='Send inference; default only validates and prints hashes')
    parser.add_argument('--state-receipt', type=pathlib.Path, help='Reviewed configuration and cache-priming receipt')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    chats = manifest['chats']
    if not 1 <= len(chats) <= 8:
        raise ValueError('Expected 1 to 8 chats')
    bodies = [body for chat in chats for body in chat['requests']]
    if not bodies or any(not chat['requests'] or chat.get('offset_s', 0) < 0 for chat in chats):
        raise ValueError('Each chat needs requests and a nonnegative offset')
    for body in bodies:
        if (body.get('model') != 'DeepSeek-V4.1-Flash-1017' or body.get('stream') is not True
                or body.get('stream_options', {}).get('include_usage') is not True
                or not 1 <= body.get('max_tokens', 0) <= 32768 or 'seed' not in body):
            raise ValueError('Explicit pinned model, seed, streamed usage and output budget required')
    plan = {'manifest_sha256': digest(args.manifest.read_bytes()),
            'payload_sha256': [digest(encoded(body)) for body in bodies], 'chats': len(chats)}
    print(json.dumps(plan, indent=2))
    if not args.run:
        return
    if args.base != 'http://127.0.0.1:8888' or not args.key_file or not args.state_receipt:
        raise ValueError('Run on the approved head via loopback, with key-file and state-receipt')
    state = json.loads(args.state_receipt.read_text())
    # Evidence is supplied by the maintenance operator; this runner cannot verify deployment identity.
    if state.get('admission_tokens') != 0 or state.get('interleave_ms') != 250:
        raise ValueError('Only the flag-0, 250 ms scheduling configuration is accepted')
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'manifest.json').write_bytes(args.manifest.read_bytes())
    (args.out/'state-receipt.json').write_bytes(args.state_receipt.read_bytes())
    client = Client(args.base, args.key_file.read_text().strip())
    before = client.idle()
    (args.out/'before.json').write_text(json.dumps(before, indent=2))
    start = time.monotonic()

    def chat_run(index, chat):
        time.sleep(max(0, start+chat.get('offset_s', 0)-time.monotonic()))
        rows = []
        for wave, body in enumerate(chat['requests']):
            row = client.request(body, args.out/f'chat-{index}-wave-{wave}.sse')
            row.update(chat=index, wave=wave, start_offset_s=time.monotonic()-start-row['elapsed_s'])
            (args.out/f'chat-{index}-wave-{wave}.json').write_text(json.dumps(row, indent=2))
            rows.append(row)
            if not row['complete']:
                break
        return rows

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(chats)) as pool:
        jobs = [pool.submit(chat_run, i, chat) for i, chat in enumerate(chats)]
        rows = [row for job in jobs for row in job.result()]
    elapsed = time.monotonic()-start
    # Counter closure must observe completion, not just the last SSE packet.
    after, closed = client.metrics(), None
    for _ in range(40):
        closed = closure(before, after, rows)
        if closed['clean']:
            break
        time.sleep(.25)
        after = client.metrics()
    closed = closure(before, after, rows)
    closed['clean'] = closed['clean'] and len(rows) == len(bodies)
    result = dict(plan, wall_s=elapsed, before=before, after=after, rows=rows, accounting=closed)
    (args.out/'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'wall_s': elapsed, 'accounting': closed}))
    if not closed['clean']:
        raise SystemExit('Run retained but excluded: incomplete or unmatched token accounting')


if __name__ == '__main__':
    main()
