#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fetch pinned public source and prepare a recipe overlay; never build or start a server."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

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
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists():
        p.error('--output must not exist')
    pins = json.loads((ROOT/'provenance/pins.json').read_text())
    patch = ROOT/'patches/9999-cache-io-backpressure.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest() != pins['publication_patch_sha256']:
        raise RuntimeError('Overlay patch does not match provenance')
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
    for name, wanted in expected.items():
        if hashlib.sha256((engine/name).read_bytes()).hexdigest() != wanted:
            raise RuntimeError('Baseline mismatch: '+name)
    run('git', 'apply', '--check', str(patch), cwd=engine)
    shutil.copyfile(patch, recipe/'zig/patches'/patch.name)
    (out/'preparation.json').write_text(json.dumps({
        'recipe_commit': pins['recipe']['commit'], 'engine_commit': pins['engine']['commit'],
        'upstream_patches': len(patches), 'base_file_hashes_verified': True,
        'overlay_apply_check_passed': True, 'model_downloaded': False,
        'image_built': False, 'service_started': False,
    }, indent=2)+'\n')
    print('Prepared source-only recipe:', recipe)
    print('Reconstructed baseline for CPU tests:', engine)
    print('No model, image build, host configuration or service was changed.')


if __name__ == '__main__':
    main()
