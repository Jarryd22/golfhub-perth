"""Check the captured nine-case UI evidence; does not run the application."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
before = json.loads((root / 'before/probe.json').read_text())
after = json.loads((root / 'after/probe.json').read_text())
assert before['callback_errors'] == after['callback_errors'] == []
checks = []
for old, new in zip(before['cases'], after['cases'], strict=True):
    assert old['scenario'] == new['scenario']
    assert old['submitted_context'] == old['render_context']
    assert new['submitted_context'] == new['render_context'] == old['submitted_context']
    if old['injected_io_errors']:
        assert old['fetch_returned_dates'] == []
        assert new['fetch_returned_dates'] == new['submitted_context']['dates']
        assert all(new['returned_exact_downloads'].values())
        assert len(new['injected_io_errors']) == len(old['injected_io_errors'])
        assert new['live_fallback_contexts'] == []
        assert [(row['time'], row['spots']) for row in new['rendered_rows']] == [('10:00 am', 4)]
        assert all(item['bytes_unchanged'] for item in new['local_cache'].values())
        assert all(not item['stored_matches_download'] for item in new['local_cache'].values())
        if 'old' in old['scenario']:
            assert [(row['time'], row['spots']) for row in old['rendered_rows']] == [('8:00 am', 4)]
        elif 'single' in old['scenario']:
            assert old['live_fallback_contexts'] == [old['submitted_context']]
        else:
            assert old['header'] == 'SHARED CACHE UNAVAILABLE'
        if 'multi' in new['scenario']:
            assert new['header'] == 'SHARED CACHE / 2 OF 2 DAYS'
        checks.append({'scenario': old['scenario'], 'passed': True,
                       'outcome': 'Downloaded data now displayed despite failed persistence; source context and local bytes preserved'})
    else:
        for field in ('fetch_returned_dates', 'returned_exact_downloads', 'submitted_context',
                      'render_context', 'live_fallback_contexts', 'header', 'status',
                      'labels', 'rendered_rows', 'day_count', 'local_cache'):
            assert old[field] == new[field], (old['scenario'], field)
        checks.append({'scenario': old['scenario'], 'passed': True,
                       'outcome': 'Valid-save, validation or transport control unchanged'})
result = {'diagnostic_cases': len(checks), 'passed': len(checks),
          'cases': checks, 'note': 'Evidence comparisons, not additional unit-test methods.'}
(root / 'ui-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
