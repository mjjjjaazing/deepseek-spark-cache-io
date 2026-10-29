#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reconstruct both public overlays and run CPU checks; never contact a model server."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def verify_files(source, hashes):
    for name, wanted in hashes.items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != wanted:
            raise RuntimeError('Source mismatch: '+name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True, help='Prepared engine-base, before either public overlay')
    p.add_argument('--zig', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True, help='New output directory outside the source')
    a = p.parse_args()
    source, zig, out = a.source.resolve(), a.zig.resolve(), a.out.resolve()
    if out.exists() or source == out or source in out.parents:
        p.error('--out must be new and outside --source')
    if subprocess.check_output([str(zig), 'version'], text=True).strip() != '0.17.0':
        p.error('Requires Zig 0.17.0')
    shared = json.loads((ROOT/'provenance/shared-prefix.json').read_text())
    pins = json.loads((ROOT/'provenance/pins.json').read_text())
    verify_files(source, json.loads((ROOT/'provenance/base-file-hashes.json').read_text()))
    verify_files(source, shared['baseline_file_hashes'])
    out.mkdir(parents=True)
    candidate = out/'candidate'
    shutil.copytree(source/'zig', candidate/'zig')
    for name, wanted in [('9999-cache-io-backpressure.patch', pins['publication_patch_sha256']),
                         (shared['patch'], shared['publication_patch_sha256'])]:
        patch = ROOT/'patches'/name
        if hashlib.sha256(patch.read_bytes()).hexdigest() != wanted:
            raise RuntimeError('Patch provenance mismatch: '+name)
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=candidate, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=candidate, check=True)
    verify_files(candidate, shared['publication_file_hashes'])
    env = dict(os.environ, ZIG=str(zig), ZIG_GLOBAL_CACHE_DIR=str(out/'zig-cache'))
    for name in ['TF_DS_SHARED_PREFIX_TOKENS', 'TENSORFOLD_STREAM_TIMING',
                 'TF_SPILL_IO_BACKPRESSURE', 'TF_DS_PREFILL_ADMIT_TOKENS']:
        env.pop(name, None)
    checks = [('server-and-host', ['bash', str(candidate/'zig/tests/server/zig_test.sh')])]
    for module in ['shared_checkpoint', 'response_timing']:
        checks.append((module, [str(zig), 'test', '-lc', str(candidate/f'zig/src/server/{module}.zig')]))
    results = []
    for label, command in checks:
        proc = subprocess.run(command, cwd=candidate, env=env, capture_output=True, text=True, timeout=300)
        log = proc.stdout+proc.stderr
        (out/(label+'.log')).write_text(log)
        passed = proc.returncode == 0 and 'tests passed.' in log
        results.append(dict(check=label, exit=proc.returncode, passed=passed))
        (out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
        print(json.dumps(results[-1]), flush=True)
        if not passed:
            raise SystemExit('CPU check failed; see saved log')


if __name__ == '__main__':
    main()
