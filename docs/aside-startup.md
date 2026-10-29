# Fresh Aside chat startup: exact shared-prefix checkpoints

This is a separate opt-in extension to [MiaAI-Lab’s pinned recipe](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/tree/27741e176a9e5b98c10c9c7d012fd3e4fcdc19b6), on top of the original I/O gate. It uses TensorFold’s existing prefix cache and shared checkpoint machinery. [Attribution](attribution.md), [NOTICE](../NOTICE) and all inherited licenses continue to apply. No endorsement or exhaustive novelty claim is implied.

## Diagnosis and change

Two new concurrent Aside chats initially sent about 32.8k tokens each, including a 99,117-character system message, 17 tool definitions, and no images. Turning the image-I/O gate off/on gave essentially the same first-content times: 17.281/34.547 seconds off, 17.150/34.391 seconds on. That gate cannot resolve a text-only initial prefill.

An in-memory comparison of owned test requests found a 23,973-token exact common prefix. Three per-chat directory paths differed later in the system message; existing checkpoint hints fell after those differences. The comparison did not change the actual requests. No prompt text or private paths are included in the public dataset.

`TF_DS_SHARED_PREFIX_TOKENS=22528` adds one aligned checkpoint before that volatile metadata. The normal cache machinery still validates the actual token prefix. It does not strip directory paths, rewrite messages, force cache keys, share differing suffixes, or change sampling or numerical computation. A new chat must still process its uncached suffix. Existing cache behavior subsequently found 24,576 reusable tokens for the tested fresh chats.

The setting is off when absent or invalid. A valid value is a positive multiple of 2,048, at least 2,048, and leaves at least 2,048 system-prefix tokens after the checkpoint. Direct prompt requests with no identified system prefix do not get this extra checkpoint. **22,528 is a measured value for this client setup, not a universal preset.** Different client instructions, tools or versions may have a shorter common prefix or different useful boundary. Measure your own prefix and observed reuse.

`TENSORFOLD_STREAM_TIMING=1` independently enables metadata-only logs recording first nonempty reasoning, content and tool events after SSE emission. No message text is logged by this feature. Missing events use `-1`. A diagnostic A/B tag recognizes the synthetic marker in user messages; other requests use `-`. The tag is diagnostic metadata, not authentication or proof that a request belongs to a benchmark. Unrelated inference must also be excluded using request and whole-run token accounting.

## Source preparation and CPU checks

From this repository, using a new output directory:

```sh
python3 tools/prepare.py --with-shared-prefix --output /path/to/new-startup-source
python3 tools/run_shared_prefix_tests.py \
  --source /path/to/new-startup-source/engine-base \
  --zig /path/to/zig-0.17.0 \
  --out /path/to/new-startup-tests
python3 tools/check_startup_results.py
```

The preparation command downloads only the pinned public source, applies MiaAI’s 26 baseline patches, verifies source hashes, checks both overlays in order, and installs them into the new recipe checkout. It leaves `engine-base` before both overlays for CPU testing. It does not download weights, build images, contact hosts or start a service. Without `--with-shared-prefix`, preparation retains the original I/O-only behavior.

The CPU runner reconstructs both patches in its own directory and checks publication source hashes, runs the server/host suites, then explicitly tests both new helper modules. The measured runtime passed 84 server and 97 host tests; helper modules are checked separately because lazy module reachability should not be assumed to run their tests. Public reproduction results are recorded in [startup-publication-checks.json](../results/startup-publication-checks.json).

The [source manifest](../provenance/shared-prefix.json) records baseline, measured and published hashes. Publication adds only two module-documentation notice lines to each of four files. Runtime and test bodies match the measured implementation after those notices are removed. Existing CUDA kernels and worker code were not changed; no binaries are redistributed. Rebuilding the commented public source need not produce the private measured binary hash.

## Enable and reproduce responsibly

Use the prepared recipe’s normal build process and your existing single supervisor during an idle maintenance window. Keep your original image, launch settings and per-rank cache directories. Use a separate candidate cache root; never spoof compatibility identities or merge unknown KV contents. Preserve authentication, model/precision pins, context, shared pool, slots, output limits and restart guards. See [deployment.md](deployment.md).

After rebuilding, configure `scripts/local.sh`:

```sh
export TF_SPILL_IO_BACKPRESSURE=1
export TF_DS_SHARED_PREFIX_TOKENS=22528
export TENSORFOLD_STREAM_TIMING=1
```

The pinned recipe forwards these variables to both ranks. Check the actual image and environment on both nodes, authenticated model discovery and real inference. The timing flag is optional. To disable the checkpoint in the candidate image, unset it or use `0`, then restart through the supervisor. Full rollback restores the saved original image/configuration/cache together.

For the numerical control, use a server already prepared on loopback with the original I/O overlay, a separate empty control cache, and the checkpoint disabled. This runner sends two deterministic synthetic requests, each allowing 512 output tokens. This small control proves output identity, **not realistic interactive latency**:

```sh
python3 benchmarks/shared_prefix_control.py control --out /path/to/control \
  --key-file /path/to/your-key --run
```

Then prepare the candidate with both patches, a separate empty cache, and the 22,528 checkpoint; preserve all other settings. Run:

```sh
python3 benchmarks/shared_prefix_control.py candidate --out /path/to/candidate \
  --key-file /path/to/your-key --reference /path/to/control --run
```

Without `--run`, these commands send no inference. The runner never SSHes, restarts, changes environment, or clears caches. It checks request identity, full returned token arrays, content hashes, actual checkpoint reuse, within-case token accounting, and counter continuity between cases. A failed or contaminated run must be retained as a failure, not silently retried into a favorable number.

For real client validation, use dedicated test chats in your own Aside profile, the same provider/model, high reasoning and normal output allowance. Have both new chats concurrently open their own local fixture page, read different codes, close only their own tabs, and answer. Observe actual page requests, returned codes and tab cleanup. Record the first initial request’s streamed reasoning/content/tool timestamps separately from committed-message polling or actual screen-paint instrumentation. Include automatic title/helper requests in whole-run accounting. Do not read existing personal chats for a performance test.

Use new chats for each pair: empty candidate cache; three repeat pairs with shared instructions available; a new pair after a supervised restart with actual committed disk restore. Keep content correctness separate from exact answer formatting. Do not change reasoning or output limits to improve latency. Pause unrelated inference and exclude contaminated runs. Predetermine targets and retain failures; the post-observation review in our campaign is disclosed below. Our private account-specific browser and service controllers are not shipped as a portable automation script; adapt this procedure to your client without copying private settings.

## Measurements and what they mean

All real client main requests kept high reasoning and a 16,384-token output allowance. The server default stayed 32,768. Candidate initial prompts were about 33.7k tokens versus about 32.8k in the earlier off/on arms. Dynamic client/session metadata prevents calling these byte-identical requests. The baseline used a metadata recorder and the candidate used native timing. Synthetic controls separately used identical requests and exact output comparisons.

| Phase | Chat A first signal | Chat B first signal | Cached tokens A / B | Aside committed observation A / B |
|---|---:|---:|---:|---:|
| I/O off | 34.547 s | 17.281 s | 0 / 0 | Not included in sanitized table |
| I/O on | 34.391 s | 17.150 s | 0 / 0 | Not included in sanitized table |
| Candidate empty-cache pair | 17.652 s | 24.409 s | 0 / 22,528 | 26.315 / 26.828 s |
| Candidate fresh pair 1 | 11.481 s | 4.836 s | 24,576 / 24,576 | 13.925 / 14.685 s |
| Candidate fresh pair 2 | 10.315 s | 6.049 s | 24,576 / 24,576 | 15.575 / 14.054 s |
| Candidate fresh pair 3 | 10.282 s | 4.922 s | 24,576 / 24,576 | 15.680 / 14.922 s |
| After restart, original gate | **12.114 s** | 5.029 s | 24,576 / 24,576 | 14.979 / 17.768 s |
| New confirmation after adoption review | 11.577 s | 4.993 s | 24,576 / 24,576 | 14.991 / 15.751 s |

“First signal” is the first nonempty streamed reasoning, content or tool event. It is not always first visible content text. Final confirmation first content was 11.577/12.473 seconds. Committed observations come from Aside’s API at 250ms polling; they are **not exact live screen-paint timestamps**. Letters identify fixture tasks, not queue priority; the README sorts each pair for compact presentation.

Relative to the original I/O-on pair, final confirmation mean first-signal wait fell 67.9% and mean first-content wait fell 53.3%. Those are descriptive ratios of small observed pairs, not causal estimates from identical real-client inputs, token/s gains or a latency SLA. The broader startup data are retained rather than showing only the best pair. The truly empty-cache bootstrap was still 17.652/24.409 seconds. Cache eviction, client instruction changes, and new binary identities can require another bootstrap.

Both restart trials recorded one committed disk restore shared by two initial requests. Each of the six candidate pairs had clean whole-run token accounting, both browser tasks correct and zero owned tabs remaining. Two deterministic native control pairs matched full token IDs and content hashes; the second candidate request reused exactly 22,528 tokens with ~4.889s TTFT versus ~14.20s control.

## Failed checks and adoption decision

- The I/O-off pilot returned correct codes with explanatory prose. Its strict five-digit-only harness marked it failed and automatically restored the baseline. Final whole-run counter closure is unavailable. Its timing receipts are retained; it is not described as a fully passed arm.
- The I/O-on browser tasks and accounting passed. Its controller later timed out during a bounded hold and restored production; this was not a model/task failure.
- The original candidate gate required each first signal within 12 seconds and committed observation within 18 seconds. Post-restart chat A took **12.114 seconds**, so that gate **failed** and automatic rollback happened.
- A disclosed post-observation review adopted a practical 15-second first-signal / 20-second committed-observation bound. A **new** pair after another start passed, including an actual disk restore. Only then was the candidate retained. The old gate is not retrospectively marked passed; this is not independent validation of a pre-registered 15-second hypothesis.

This startup campaign does not establish an all-day soak, population p95, arbitrary-client performance, long-conversation behavior, image performance, or higher concurrency for the new patch. The earlier 351-request I/O campaign is separate evidence and must not be presented as testing the new checkpoint. No new kernel, raw decoding acceleration, reduced reasoning or shorter allowed answers account for this change.

## Public evidence and privacy

[aside-startup.json](../results/aside-startup.json) contains allowlisted per-chat durations/counts, phase outcomes and synthetic exact-control hashes. `tools/check_startup_results.py` checks the comparisons and keeps original failure separate from adoption review. It contains no session/request IDs, hostnames, addresses, private paths, chat text, credentials, weights or KV data. Raw client receipts and operational controllers remain private. The original I/O dataset and licenses remain unchanged.
