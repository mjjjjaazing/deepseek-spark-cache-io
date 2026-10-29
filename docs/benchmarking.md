# Reproducing hardware workloads

These runners are portable API clients, not deployment controllers. They use an already prepared server at `http://127.0.0.1:8888` and only send inference with `--run`. Run them on the serving head, using your own private key file. They never SSH, restart services, copy caches, change clocks or modify a model.

## Before comparing

Use the same patched binary on both arms and change only `TF_SPILL_IO_BACKPRESSURE=0` versus `1`. Hold model/quantization/kit, context, shared pool, parallelism, output allowance, prompt-cache budget, spill policy, sampling and interleave constant. Record actual image/command/environment identities yourself; a benchmark label does not verify deployment configuration. The measured profile is in [deployment.md](deployment.md).

Pause other inference. Every cohort checks prompt/generation counters against its own usage. The public harness also refuses counter changes between cohorts before sending another request, and the original campaign checked closure across complete arms. Do not discard failures and keep retrying until a favorable timing appears. Preserve raw SSE, failures and any exclusion reason. Our reports use time reduction: `100 * (1 - on_seconds / off_seconds)`.

## Seed preparation

On a disposable empty cache using the patched binary with the policy off, run:

```sh
python3 benchmarks/seed_cycle.py off --out /path/to/new-seed-run --key-file /path/to/private-key --run
```

This reproduces the historical cold-to-warm seed workload, including eight image histories and a 90k text prefix. Seed setup used short retrieval allowances; it is outside the timed normal-limit comparison. The timed main suite changes every request allowance to 32,768.

Wait for cache writes to settle, stop through your existing supervisor, and freeze the resulting cache on each rank. Make independent copies of each node’s own seed for the two arms. Preserve compatibility identity and compare opaque file manifests. Never copy actively written cache files or substitute a cache from a different engine identity.

The seed request used by the main suite is:

```text
/path/to/new-seed-run/results/off/prime90k-attempt0/payloads.json
```

The generator reproduces the same request bodies, but fresh cache metadata can differ between machines/runs. The important controlled comparison is that both arms of your run start from identical frozen copies on each respective rank. We do not distribute KV cache data.

## Main normal-limit comparison

Start the off arm against one frozen copy, then run:

```sh
python3 benchmarks/suite.py off   --out /path/to/new-off-run   --seed-request /path/to/new-seed-run/results/off/prime90k-attempt0/payloads.json   --key-file /path/to/private-key --run
```

Set up the on arm against the other identical frozen copy and repeat with `on` and a new output directory. The suite has 88 requests and records the queued-restore precondition. It covers growing histories, eight-image concurrency, real long generation, mixed arrivals, and feature checks. Compare request hashes, output token hashes, cache-counter deltas, complete-run accounting and per-request latency—not just aggregate completion time.

## Ordered conversation confirmation

Simultaneous client indices do not guarantee arrival order. Use the deliberately staggered confirmation for that question:

```sh
python3 benchmarks/ordered_conversations.py off --out /path/to/new-ordered-off --key-file /path/to/private-key --run
python3 benchmarks/ordered_conversations.py on --out /path/to/new-ordered-on   --reference /path/to/new-ordered-off/results/fairness-v2-off   --key-file /path/to/private-key --run
```

The operator must switch the service between those commands. Use separate empty caches, or identical frozen caches created before these fixtures, and fresh server processes for the ordered arms. Ensure the unique initial prefixes are cold in both arms; the runner refuses unexpectedly warm initial contexts. It records achieved send offsets and checks exact outputs and the original per-request thresholds. Reusing the same fixtures on an already warmed server is not a new cold experiment.

## Finite sustained trial

```sh
python3 benchmarks/soak.py canary --out /path/to/new-trial --key-file /path/to/private-key --run
```

This runs for at least 30 minutes and eight rounds, appending actual assistant replies to four histories and alternating 1/4/8-stream generation. The allowance remains 32,768. It verifies original-code recall and full-run token closure. Keep your existing failure supervision and rollback budget; this public client intentionally does not control systemd or Docker.

For persistence verification, settle writes and perform a supervised restart. Replay the last conversation payloads from the trial, compare exact output hashes, require substantial cached-token reuse and real disk commits, and repeat the feature checks. Do not force old compatibility fingerprints. Preserve the previous image/configuration/cache so a failed candidate can be rolled back.

All tools default to no inference unless `--run` is supplied. Their output directories may contain prompts, responses or errors; review them before sharing. `runs/`, SSE files, environment files and archives are gitignored.
