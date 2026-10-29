# Validation and limitations

## Recorded coverage

- Main matched off/on sweep: 88 requests per arm, 58,189 generated tokens per arm, all request and output-token hashes matching. The normal output allowance was 32,768; one actual answer generated 13,785 tokens.
- Four conversations grew from about 50k to 106k tokens; eight approximately 90k image histories were tested cold and over three repeat turns.
- One-, four- and eight-stream generation, long generation alongside fresh requests, and image/reasoning/tool checks were included.
- Additional ordered-arrival confirmation: 20 requests per arm, fresh prefixes, actual prior assistant replies, client sends separated by 0.3 seconds. The original per-request thresholds and exact outputs passed; maximum added first-token wait was 0.972 seconds.
- Retained-candidate trial: 1,855.87 seconds (30.93 minutes), 15 rounds, 128 requests, 196,304 generated tokens, histories up to 150,925 tokens. Later prompts retrieved the original code from history without repeating it, then generated substantial answers.
- After a real restart, four histories restored 147,456 / 147,456 / 149,504 / 149,504 tokens through four disk commits with exact long-output hashes. Image/reasoning/tool checks also passed.
- Overall: 351 completed validated requests, 315,937 generated tokens, 108 paired output comparisons, plus four exact comparisons across restart. No unplanned restart or matching engine-fault log entry was observed in these runs.
- CPU host suite: 89 baseline tests, 97 candidate tests, with the intended baseline-failing starvation reproduction. The published source has only attribution-comment differences from the measured runtime/test bodies.

## Keep the original failed checks visible

The original per-client-index latency gate flagged 19 comparisons in simultaneous four/eight-request cohorts. They are retained in `results/latency-review.json`; they were not silently erased.

Zero-offset client indices were not reliable arrival-priority labels. Repeats under the unchanged enabled policy themselves moved individual first-token waits by up to 7.86 seconds while sorted response-time ranks stayed stable. A documented post-observation review therefore checked every observed sorted latency rank for simultaneous batches, preserving the original tolerances. It kept strict per-request checks for deliberately staggered arrivals. This review passed, but does not promise an individual client a faster response or fixed order.

Because mixed text/image histories needed stronger confirmation, a fresh comparison with 0.3-second separated client sends was required before the trial. It passed the original per-request gates as well as exact payload/output checks. This follow-up compared the original production image against the enabled candidate; the primary 88-request A/B comparison used the same candidate binary in both arms.

The thresholds were: ordinary batch time at most max(1 second, 10%) worse; per-request TTFT at most max(1 second, 10%) worse; per-request completion at most max(2 seconds, 10%) worse. The targeted stress required at least 10% less batch time, a committed restore, and fresh-image delay no more than max(2 seconds, 5%). All correctness, coverage and whole-run token accounting checks were required.

## Excluded attempt

The first ordered-arrival confirmation overlapped unrelated inference. Its owned replies were correct, but aggregate token accounting did not close. That attempt was excluded, other work was paused, and fresh-prefix v2 was run. The exclusion is recorded; these requests are not included in the 351 successful-validation count.

## Interpretation

The 35.46% result is for a particular queued restore / long-image collision. The 78.17% result is the median of three successive eight-history repeat turns in one paired workload sweep. Those warm caches are treatment outcomes of the same cold sequence, not identical independently cloned warm snapshots. Baseline recomputed one history on each repeat; the enabled arm reused cached tokens for every history.

Cold eight-history load measured 1.2% longer and the competing image in the targeted collision waited 1.24 seconds longer. Raw generation was effectively unchanged. Small differences around 1% are not established universal effects.

These are deterministic synthetic workloads on one physical pair, not population-p95 evidence, high-resolution browser-workflow coverage, an exhaustive fault campaign, or a full-day soak. Queue order can vary. Prolonged hardware faults and other model/kit revisions need their own validation. No claim is made to fix every upstream cache issue.

## Public evidence

`results/measurements.json` contains per-response timings, token counts, output hashes, cache-counter deltas and accounting for all 351 included requests. It excludes generated text, private host inventories, credentials, local paths and KV data. The original record hashes are provenance anchors; private unredacted operational archives are not published. The benchmark source lets operators reproduce the synthetic payloads and retain their own SSE logs.

The workload bodies have been checked against the archived main-run payloads using an offline replay; this check sends no inference. Host tests and source reconstruction are also rechecked for the public package. The rebuilt distribution itself has not been re-benchmarked on another pair, and no bit-identical binary-build guarantee is made.

### Hash precision

The engine emits only the first 12 hex characters of a SHA-256 token-ID digest. The public dataset labels that field `token_sha256_prefix_12`; it is not a full digest or a retained token-ID array. Publication verification additionally compares full visible-content and reasoning SHA-256 hashes and canonical tool-call semantics for all 108 pairs and the four restart comparisons. Generated tool-call IDs are excluded from semantic comparison. All these comparisons pass.
