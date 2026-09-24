"""Post-inference benchmark comparison; imports no inference runtime."""
import argparse
import csv
import json
from pathlib import Path
from app import selection, settings


def evaluate(path, truth):
    raw = selection.model_result(json.loads(path.read_text()))
    original = selection.digest(raw)
    assert raw['run']['scored_pages'] == raw['run']['total_pages']
    assert raw['run']['model_forward_seconds'] > 0
    policy = selection.select_pages(raw['pages'], settings.preset('benchmark_direct'), truth)
    sweep = selection.threshold_sweep(raw['pages'], truth)
    exports = selection.export_selection(raw, policy, path.parent)
    assert selection.digest(raw) == original
    return {'source': str(path), 'input_sha256': raw['inputs']['sha256'], 'run': raw['run'],
            'selection': policy, 'sweep': sweep, 'selection_exports': exports}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--truth', required=True)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    raw = json.loads(args.run.read_text())
    truth = selection.parse_ground_truth(args.truth, len(raw['pages']))
    result = evaluate(args.run, truth)
    if args.baseline:
        baseline_raw = selection.model_result(json.loads(args.baseline.read_text()))
        if result['input_sha256'] != baseline_raw['inputs']['sha256']:
            raise ValueError('Baseline inputs differ; cannot compare these benchmark runs')
        result['baseline'] = evaluate(args.baseline, truth)
    folder = args.run.parent / 'semantic-evaluation'
    folder.mkdir(exist_ok=True)
    out = folder / (args.run.stem + '_evaluation.json')
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    with out.with_suffix('.csv').open('w', newline='') as handle:
        rows = result['sweep']['rows']
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'evaluation': str(out), 'metrics': result['selection']['benchmark_metrics'],
                      'selected': result['selection']['final_selected_pages'],
                      'baseline_metrics': result.get('baseline', {}).get('selection', {}).get('benchmark_metrics'),
                      'highest_full_recall': result['sweep']['highest_threshold_full_recall'],
                      'timing': {k: result['run'][k] for k in ['classification_seconds','model_forward_seconds','average_page_seconds','model_reused']}}, indent=2))


if __name__ == '__main__':
    main()
