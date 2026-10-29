#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate exact synthetic request manifests; does not contact a server."""
import argparse
import base64
import json
import pathlib
import random
import struct
import zlib

WORDS = 'river mountain signal engine garden theory market winter method bridge letter window voice paper field project browser request result server history memory task document action page button value function'.split()


def prose(words, seed):
    rng = random.Random(seed)
    return ' '.join(rng.choice(WORDS) for _ in range(words))


def image():
    # Solid blue PNG, no external libraries or remote assets.
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    raw = b''.join(b'\0'+b'\x20\x40\xe0'*32 for _ in range(32))
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,32,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    return 'data:image/png;base64,'+base64.b64encode(png).decode()


def request(messages, budget=16, reasoning='none'):
    return dict(model='DeepSeek-V4.1-Flash-1017', messages=messages, max_tokens=budget,
                temperature=0, top_p=.95, top_k=20, seed=1234, reasoning_effort=reasoning,
                stream=True, stream_options={'include_usage':True})
