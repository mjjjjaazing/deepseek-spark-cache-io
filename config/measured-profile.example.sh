# Measured profile, NOT universal hardware defaults. Review memory headroom first.
# Network identity, credentials, model pins and machine-specific paths are omitted.
CONTEXT=262144
POOL=1048576
PARALLEL=8
MAX_TOKENS=32768
SPILL_GIB=64
KV_SHARD=0
PREFILL_INTERLEAVE_MS=250

# Our launch additionally passed --prompt-cache-gib 0.5 to tensorfold-native serve.
# Existing authentication, memory guards and GPU clock policy remained unchanged.
# Keep a separate local spill directory on each node, outside model/NFS folders.
# The alternative experimental prefill-admission policy was disabled in our tests;
# it is not included in this repository or required by this patch.
