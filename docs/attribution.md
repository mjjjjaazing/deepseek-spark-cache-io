# Attribution and scope of this contribution

This repository builds on [MiaAI-Lab’s recipe](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks). Its pinned [CREDITS.md](../licenses/MiaAI-CREDITS.md) and [NOTICE](../licenses/MiaAI-NOTICE) are retained verbatim.

| Component | Credit |
|---|---|
| Model, weights, DSpark draft blocks, reference inference | DeepSeek |
| EAQ v1 EXL3 pack and two-Spark recipe/integration | MiaAI-Lab / Mia-AiLab |
| Native Zig engine, server, lane core and CUDA runtime | Ash Hart and TensorFold contributors |
| DeepSeek-V4.1 family, model paths, distributed ring and vision integration | BertholomusAI / Albert Lee and credited contributors |
| EXL3 format and quantizer | turboderp / ExLlamaV3 |
| Spill/parking/continuation port and related fixes | Robert Wojciechowski (`wojo`), as credited in the recipe |
| Block-tier design and spill checks/fixes | BadAd84, as credited in the recipe |
| Existing prefill/decode interleave | Coinupbtc, recipe PR #5 |
| Mixed-pack support present in the pinned baseline | Mykhailo Tamarin; our measurements used EAQ v1 |

Our contribution is the opt-in long-image I/O admission gate, its regression tests, and the measurement/reproduction material here. We did not create the spill cache, make DeepSeek’s kernels faster, change quantization, or invent the recipe’s distributed execution.

MiaAI’s deployed profile and our measured profile are not identical to untouched recipe defaults. For example, the pinned recipe defaults to four streams, a 1,048,576-token context and disabled spill, while our controlled profile used eight streams, a 262,144-token request context, a 1,048,576-token shared pool and 64 GiB spill per node. Both sides of the primary A/B comparison used that same measured profile. The percentages isolate the new switch; they must not be advertised as a comparison against all stock defaults.

Existing contributor notices are in [../licenses/](../licenses/). No endorsement or exhaustive novelty claim is implied, and no claim is made that this fixes upstream issue #75 or every cache-related failure.
