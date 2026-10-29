#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate the public dataset and recompute the headline time reductions."""
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent.parent


def main():
    data = json.loads((ROOT/'results/measurements.json').read_text())
    records = data['records']
    groups = {}
    for row in records:
        assert row['accounting']['clean']
        assert all(r['complete'] for r in row['responses'])
        assert row['accounting']['expected']['prompt_tokens_total'] == sum(r['prompt_tokens'] for r in row['responses'])
        assert row['accounting']['expected']['generation_tokens_total'] == sum(r['completion_tokens'] for r in row['responses'])
        assert row['accounting']['expected'] == row['accounting']['delta']
        for response in row['responses']:
            assert len(response['token_sha256_prefix_12']) == 12
            assert all(len(response[k]) == 64 for k in ['content_sha256','reasoning_sha256','tool_call_semantics_sha256'])
        groups.setdefault(row['phase'], {})[row['case']] = row
    count = sum(len(r['responses']) for r in records)
    tokens = sum(x['completion_tokens'] for r in records for x in r['responses'])
    assert count == data['request_count'] == 351
    assert tokens == data['generated_tokens'] == 315937
    expected = {'off': 88, 'on': 88, 'fairness-v2-off': 20, 'fairness-v2-on': 20, 'canary': 128, 'persisted': 7}
    for phase, wanted in expected.items():
        assert sum(len(r['responses']) for r in groups[phase].values()) == wanted
    matched = 0
    for before, after in [('off', 'on'), ('fairness-v2-off', 'fairness-v2-on')]:
        assert groups[before].keys() == groups[after].keys()
        for name, a in groups[before].items():
            b = groups[after][name]
            assert a['payload_sha256'] == b['payload_sha256']
            assert [[r[k] for k in ['token_sha256_prefix_12','content_sha256','reasoning_sha256','tool_call_semantics_sha256']] for r in a['responses']] == [[r[k] for k in ['token_sha256_prefix_12','content_sha256','reasoning_sha256','tool_call_semantics_sha256']] for r in b['responses']]
            matched += len(a['responses'])
    assert matched == 108
    stress = {arm: groups[arm]['normal-limit-disk-starvation-attempt0']['wall_s'] for arm in ['off', 'on']}
    warm = {arm: statistics.median(groups[arm][f'eight-image-turn-{i}-attempt0']['wall_s'] for i in [1, 2, 3]) for arm in ['off', 'on']}
    summary = json.loads((ROOT/'results/summary.json').read_text())
    assert summary['trial_duration_s'] >= 1800
    assert summary['fixed_arrival_confirmation_passed']
    restored = groups['persisted']['restored-long-conversations-attempt0']
    assert restored['cache_counters_delta']['prompt_cache_disk_hits_committed'] == 4
    assert all(r['cached_tokens'] > 100000 for r in restored['responses'])
    last = groups['canary']['conversation-14-attempt0']
    assert [[r[k] for k in ['token_sha256_prefix_12','content_sha256','reasoning_sha256','tool_call_semantics_sha256']] for r in last['responses']] == [[r[k] for k in ['token_sha256_prefix_12','content_sha256','reasoning_sha256','tool_call_semantics_sha256']] for r in restored['responses']]
    print(json.dumps({'validated_requests': count, 'generated_tokens': tokens, 'exact_paired_outputs': matched,
        'stress_time_reduction_pct': 100*(1-stress['on']/stress['off']),
        'eight_history_time_reduction_pct': 100*(1-warm['on']/warm['off']),
        'original_per_index_flags_retained': not summary['original_strict_checks_passed'],
        'ordered_confirmation_passed': True, 'restart_output_hashes_match': True}, indent=2))


if __name__ == '__main__':
    main()
