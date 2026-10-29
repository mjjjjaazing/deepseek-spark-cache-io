#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fetch pinned public source and prepare a recipe overlay; never build or start a server."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def fetch(spec, dest):
    dest.mkdir()
    run('git', 'init', '-q', str(dest))
    run('git', 'remote', 'add', 'origin', spec['url'], cwd=dest)
    run('git', 'fetch', '-q', '--depth', '1', 'origin', spec['commit'], cwd=dest)
    run('git', '-c', 'advice.detachedHead=false', 'checkout', '-q', '--detach', 'FETCH_HEAD', cwd=dest)
    if run('git', 'rev-parse', 'HEAD', cwd=dest) != spec['commit']:
        raise RuntimeError('Unexpected checkout revision')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True, help='New directory; existing paths are refused')
    p.add_argument('--with-shared-prefix', action='store_true', help='Also prepare the optional fresh-chat checkpoint and timing patch')
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists():
        p.error('--output must not exist')
    pins = json.loads((ROOT/'provenance/pins.json').read_text())
    patch = ROOT/'patches/9999-cache-io-backpressure.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest() != pins['publication_patch_sha256']:
        raise RuntimeError('Overlay patch does not match provenance')
    overlays = [patch]
    shared = None
    if a.with_shared_prefix:
        shared = json.loads((ROOT/'provenance/shared-prefix.json').read_text())
        extra = ROOT/'patches'/shared['patch']
        if hashlib.sha256(extra.read_bytes()).hexdigest() != shared['publication_patch_sha256']:
            raise RuntimeError('Shared-prefix patch does not match provenance')
        overlays.append(extra)
    out.mkdir(parents=True)
    recipe, engine = out/'recipe', out/'engine-base'
    fetch(pins['recipe'], recipe)
    fetch(pins['engine'], engine)
    patches = sorted((recipe/'zig/patches').glob('*.patch'))
    if len(patches) != pins['public_baseline_patches']:
        raise RuntimeError('Unexpected upstream patch count')
    for item in patches:
        run('git', 'apply', '--check', str(item), cwd=engine)
        run('git', 'apply', str(item), cwd=engine)
    expected = json.loads((ROOT/'provenance/base-file-hashes.json').read_text())
    if shared:
        expected.update(shared['baseline_file_hashes'])
    for name, wanted in expected.items():
        if hashlib.sha256((engine/name).read_bytes()).hexdigest() != wanted:
            raise RuntimeError('Baseline mismatch: '+name)
    # Check the actual ordered stack without modifying the CPU-test baseline.
    with tempfile.TemporaryDirectory(prefix='overlay-check-', dir=out) as temp:
        check = Path(temp)
        shutil.copytree(engine/'zig', check/'zig')
        for item in overlays:
            run('git', 'apply', '--check', str(item), cwd=check)
            run('git', 'apply', str(item), cwd=check)
        if shared:
            for name, wanted in shared['publication_file_hashes'].items():
                if hashlib.sha256((check/name).read_bytes()).hexdigest() != wanted:
                    raise RuntimeError('Candidate mismatch: '+name)
    for item in overlays:
        shutil.copyfile(item, recipe/'zig/patches'/item.name)
    (out/'preparation.json').write_text(json.dumps({
        'recipe_commit': pins['recipe']['commit'], 'engine_commit': pins['engine']['commit'],
        'upstream_patches': len(patches), 'base_file_hashes_verified': True,
        'overlay_apply_check_passed': True, 'model_downloaded': False,
        'image_built': False, 'service_started': False,
        'overlays': [item.name for item in overlays],
        'shared_prefix_included': a.with_shared_prefix,
    }, indent=2)+'\n')
    print('Prepared source-only recipe:', recipe)
    print('Reconstructed baseline for CPU tests:', engine)
    print('No model, image build, host configuration or service was changed.')


if __name__ == '__main__':
    main()
