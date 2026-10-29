# Optional startup extension; rebuild with --with-shared-prefix first.
# 22528 is the measured Aside value, not a universal client default.
# Verify an exact stable system prefix longer than this boundary on YOUR client.
export TF_DS_SHARED_PREFIX_TOKENS=22528
# Optional metadata-only first-stream timings; disabled when unset/not exactly 1.
export TENSORFOLD_STREAM_TIMING=1
# Keep the original independently controlled I/O policy if desired.
export TF_SPILL_IO_BACKPRESSURE=1
# To disable the extra checkpoint, unset it or set it to 0, then use your supervisor.
# Never change prompt text or spoof cache compatibility fingerprints to force hits.
