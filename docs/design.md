# Design: let cache I/O progress before a long image prefill

The observed failure is host-loop starvation. A request parks while an existing prefix is being restored. A subsequent long image prefill has no between-chunk cache-service callback. When control returns after the restore deadline, the host can expire the restore before polling it, then recompute the old prompt. The roughly 40-second wait in the reproduction was not a measurement of 40-second physical NVMe latency.

The new `TF_SPILL_IO_BACKPRESSURE` switch is read once at host initialization. Only the exact value `1` enables it. It defaults off.

1. Take the next request according to the existing ready/queued precedence.
2. Follow the existing `park(job)` restore path first. Eligible restores must not be blocked behind the gate they need to satisfy.
3. For an image request, inspect its available in-memory prefix. If its uncached suffix is at most 8,192 tokens, proceed normally.
4. If a restore is loading or the cache store is busy, put the image back at the head of the same queue and service pending work. The first gate entry records a per-job timestamp.
5. Once I/O clears or the existing load-wait bound expires, continue through normal admission. At idle, use the existing polling cadence instead of spinning or sleeping past pending I/O.

The 8,192-token cutoff is an experimental heuristic, not a new public tuning API. The bound applies to this gate; it is not a global request-latency SLA. This does not guarantee every restore succeeds, especially with real disk faults or capacity pressure.

The patch preserves ordinary capacity refusal/retry behavior, cancellation, shutdown, ready/queued precedence, and decode interleave. It adds no nested admissions, new priority class, cache format, kernel, sampling rule, model precision change or speculative-decoding policy.

The eight added tests cover: a short image progressing during unrelated I/O; the reproduced long-image restore timeout; disabled behavior; existing full-tier retry/bounded fallback; cancellation and shutdown; fresh text during a pending restore; bounded waiting on permanently busy writes; and an idle/no-pending-work path that preserves the decode budget. The negative control restores the baseline host while retaining the new test, proving the reproduction fails as intended.

The public patch adds two module-documentation attribution lines to each changed file. After removing those lines, its runtime and test bodies are byte-identical to the measured implementation. Packaging does not claim a bit-identical rebuilt binary; compiler/build metadata and freshly compiled CUDA assets can differ. Benchmark build hashes remain available as provenance.
