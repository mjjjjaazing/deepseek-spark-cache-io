# Deployment notes

This extension prepares source and adds a patch; it is not a replacement cluster installer. Start with the pinned MiaAI recipe’s prerequisites, verified pair membership and a working authenticated deployment. Source preparation here never contacts a Spark or changes a service.

## Measured profile

| Setting | Measured value |
|---|---:|
| Hardware | Two DGX Spark / GB10 nodes, tensor parallel |
| Model | DeepSeek-V4.1-Flash-1017, EAQ v1 EXL3 2.9 bpw |
| Request context | 262,144 tokens |
| Shared pool | 1,048,576 tokens |
| Parallel slots | 8 |
| Default / main-test output allowance | 32,768 tokens |
| Prompt cache budget | 0.5 GiB |
| Spill capacity | 64 GiB per node |
| KV sharding | Disabled |
| Prefill interleave | 250 ms |
| New switch | Off/on for primary comparison; on for retained trial |

These values are a measured configuration, not a recommendation to copy them blindly. Authentication, model pins, memory guards and clock policy were held constant. The example files under `config/` contain no host identity or credentials.

## Integration

`tools/prepare.py` creates a new pinned recipe checkout and an engine baseline for CPU tests. The recipe copy contains `zig/patches/9999-cache-io-backpressure.patch`. Its existing Dockerfile applies engine patches in filename order, so this patch follows the recipe’s 26 existing patches. The recipe’s image identity incorporates patch contents.

Configure that checkout using your own working settings. Build with MiaAI’s documented preparation process during an idle maintenance window: the upstream build may download weights and requires substantial memory. No new build flags or replacement kernels are needed. The native HTTP module keeps its existing safe optimization mode; engine/worker modules use the existing fast build settings.

Add `export TF_SPILL_IO_BACKPRESSURE=1` to `scripts/local.sh`. The pinned `start.sh` already forwards `TF_SPILL_*` variables to both ranks. Start or restart through your existing supervisor. For a manually managed recipe with no competing supervisor, the recipe accepts `./start.sh restart --prompt-cache-gib 0.5`; use this only after reviewing its setup and service-affecting behavior.

Verify both ranks actually run the newly built image and receive the flag. Check authenticated model discovery and a real response. An environment variable on an old binary does not install the patch.

## Cache identity and rollback

Retain the original image/configuration and cache directories. Use separate local NVMe directories for a candidate; do not put spill in the model/NFS tree. Stop and settle writes before copying a cache for a controlled test. Clone the same seed on each rank for off/on arms, and compare opaque manifests. Never edit KV bytes or spoof compatibility identities to make an old cache load.

Rebuilt engine identities can create a new cache namespace, so old histories may have an initial cold turn. To disable this policy in the same candidate image, export `TF_SPILL_IO_BACKPRESSURE=0` and perform a supervised restart. To restore the entire old deployment, use the saved image, configuration and cache together.

Reserve a restoration start within your existing restart budget. Our deployment retained a three-starts-per-30-minute limit and 60-second backoff; these are operational details of our test environment, not new requirements imposed by the patch. No private service-controller scripts are shipped here.

## Optional fresh-chat checkpoint overlay

Pass `--with-shared-prefix` to source preparation to add `9999-shared-prefix-checkpoint.patch` after the I/O overlay. Rebuild through the same pinned recipe. Then review [the client-specific boundary and test procedure](aside-startup.md) before using `config/shared-prefix.example.sh`. The pinned launcher forwards `TF_DS_*` and `TENSORFOLD_*` as well as `TF_SPILL_*` to both ranks. The extra checkpoint is off by default; the timing switch is independent and optional.

Keep the original I/O validation separate from startup validation. A new binary/cache identity can require a cold bootstrap. Preserve your original image, configuration and opaque per-rank caches, and verify real new-client chats and a disk restore after restart before retaining a change. Exporting variables alone does not upgrade an existing image. Setting the checkpoint to zero and restarting disables it without disabling the I/O gate.
