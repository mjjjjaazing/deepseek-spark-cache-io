#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the sanitized startup dataset, keeping original misses separate from review."""
import json
from pathlib import Path
import statistics


def main():
    data = json.loads((Path(__file__).resolve().parent.parent/'results/aside-startup.json').read_text())
    groups = {}
    for row in data['rows']:
        groups.setdefault(row['phase'], []).append(row)
        assert 0 <= row['cached_tokens'] <= row['prompt_tokens']
        assert 0 <= row['first_signal_s'] <= row['first_content_s']
    assert set(groups) == {'io-off', 'io-on', 'cold', 'warm1', 'warm2', 'warm3', 'postrestart', 'confirmation'}
    assert all(len(rows) == 2 and {x['tag'] for x in rows} == {'A', 'B'} for rows in groups.values())
    assert data['candidate_fresh_chat_count'] == 12
    for phase in data['candidate_phases']:
        assert phase['accounting_clean'] and phase['browser_tasks_correct'] == 2
        assert phase['owned_tabs_remaining'] == 0
        if phase['phase'] in ['postrestart', 'confirmation']:
            assert phase['committed_disk_restore_delta'] > 0
    controls = {(x['arm'], x['case']): x for x in data['native_exact_controls']}
    for case in range(2):
        old, new = controls['control', case], controls['candidate', case]
        for key in ['payload_sha256', 'full_token_ids_sha256', 'content_sha256']:
            assert old[key] == new[key] and len(new[key]) == 64
        assert old['accounting_clean'] and new['accounting_clean']
        assert old['cached_tokens'] == 0 and old['output_tokens'] == new['output_tokens'] == 512
    assert controls['candidate', 1]['cached_tokens'] == 22528
    strict = data['original_gate']
    assert strict['passed'] is False and strict['automatic_rollback']
    assert max(x['first_signal_s'] for x in groups['postrestart']) == strict['miss_s'] > strict['first_signal_limit_s']
    review = data['adoption_review']
    assert review['post_observation_threshold_change'] and review['new_confirmation_passed']
    for row in groups['confirmation']:
        assert row['cached_tokens'] >= 22528
        assert row['first_signal_s'] <= review['first_signal_limit_s']
        assert row['aside_committed_observed_s'] <= review['aside_observed_limit_s']
    changes = {}
    for field in ['first_signal_s', 'first_content_s']:
        old = statistics.mean(x[field] for x in groups['io-on'])
        new = statistics.mean(x[field] for x in groups['confirmation'])
        changes[field+'_mean_reduction_percent'] = 100*(1-new/old)
    print(json.dumps(dict(candidate_chats=12, exact_native_pairs=2,
                         original_strict_gate_passed=False, reviewed_confirmation_passed=True,
                         finite_descriptive_comparison=changes), indent=2))


if __name__ == '__main__':
    main()
