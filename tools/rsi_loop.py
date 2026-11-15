"""Bounded local improvement selection for trusted candidates; NOT a sandbox."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import unittest

TARGET = Path('tender-writing/skills/bid-writing/scripts/bidflow.py')
IGNORE = shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'tmp', 'dist', '.env', '.env.*', '.venv', 'projects', 'outputs', 'output', 'company-library')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_tree(source, dest):
    # Do not follow any symlink into credentials, production data or other trees.
    for root, dirs, files in os.walk(source, followlinks=False):
        ignored = IGNORE(root, dirs + files)
        dirs[:] = [d for d in dirs if d not in ignored]
        for name in dirs + [f for f in files if f not in ignored]:
            if (Path(root) / name).is_symlink():
                raise ValueError('Snapshot contains symlink: ' + str(Path(root) / name))
    shutil.copytree(source, dest, ignore=IGNORE)


def evaluate(root, objectives, result):
    """Private subprocess entry point; driver and objective tests are frozen."""
    os.environ['RSI_CANDIDATE_ROOT'] = str(root)
    rows = {}
    for name, folder in [('regression', root / 'tests'), ('objective', objectives)]:
        suite = unittest.TestLoader().discover(str(folder), pattern='test_*.py', top_level_dir=str(folder))
        outcome = unittest.TextTestRunner(verbosity=1).run(suite)
        rows[name] = {'total': outcome.testsRun, 'failures': len(outcome.failures),
                      'errors': len(outcome.errors), 'skipped': len(outcome.skipped),
                      'unexpected_successes': len(outcome.unexpectedSuccesses),
                      'expected_failures': len(outcome.expectedFailures)}
    Path(result).write_text(json.dumps(rows), encoding='utf-8')


def run_eval(driver, root, objectives, folder, timeout):
    protected = [driver, *objectives.rglob('*.py'), *(root / 'tests').rglob('*.py')]
    hashes = {p: digest(p) for p in protected}
    result = folder / 'evaluation.json'
    # No API keys, tokens, proxies, PYTHONPATH or user startup settings inherited.
    env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT') if key in os.environ}
    env.update(HOME=str(folder), TMPDIR=str(folder), RSI_CANDIDATE_ROOT=str(root))
    with (folder / 'evaluation.log').open('wb') as log:
        proc = subprocess.Popen([sys.executable, '-I', str(driver), '--evaluate', str(root), str(objectives), str(result)],
                                cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return {'error': 'timeout'}
    if any(not p.is_file() or digest(p) != checksum for p, checksum in hashes.items()):
        return {'error': 'evaluation_integrity_changed'}
    if proc.returncode or not result.exists():
        return {'error': 'evaluation_failed', 'returncode': proc.returncode}
    return json.loads(result.read_text(encoding='utf-8'))


def failures(row):
    return row['failures'] + row['errors'] + row['unexpected_successes']


def eligible(result):
    if 'error' in result:
        return False
    guard, objective = result['regression'], result['objective']
    return (guard['total'] > 0 and failures(guard) == 0 and guard['skipped'] == 0
            and guard['expected_failures'] == 0 and objective['total'] > 0
            and objective['skipped'] == 0 and objective['expected_failures'] == 0
            and objective['errors'] == 0 and objective['unexpected_successes'] == 0)


def loop(source, objectives, candidates, output, rounds=3, patience=2, timeout=120, budget=600):
    """Each candidate is a complete replacement bidflow.py relative to the baseline."""
    if os.name != 'posix':
        raise ValueError('This runner currently requires POSIX process-group timeout handling')
    if not (1 <= rounds <= 10 and 1 <= patience <= rounds and
            math.isfinite(timeout) and 0 < timeout <= 300 and
            math.isfinite(budget) and 0 < budget <= 1800):
        raise ValueError('Invalid budget: rounds 1..10, patience 1..rounds, timeout <=300s, total <=1800s')
    source, objectives, output = map(lambda p: Path(p).resolve(), (source, objectives, output))
    if output == source or source in output.parents or output == objectives or objectives in output.parents:
        raise ValueError('Output must be outside source and objective trees')
    if output.exists():
        raise ValueError('Output must not exist (never overwrite previous runs)')
    if not (source / TARGET).is_file() or not (source / 'tests').is_dir():
        raise ValueError('Source must be a tender-writing checkout with regression tests')
    if not objectives.is_dir() or not list(objectives.glob('test_*.py')):
        raise ValueError('Supply independent objective tests before selecting candidates')
    selected = list(candidates)[:rounds]
    # Validate all selected inputs before executing any candidate.
    payloads = []
    for path in selected:
        path = Path(path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError('Candidate must be a regular local file <=2 MB')
        payloads.append((str(path.resolve()), path.read_bytes()))
    output.mkdir(parents=True)
    start = time.monotonic()
    report = {'version': 1, 'target': str(TARGET), 'limits': {'rounds': rounds, 'patience': patience,
              'evaluation_seconds': timeout, 'total_seconds': budget}, 'rounds': [], 'accepted': None,
              'stop': None, 'scope': 'trusted local candidates only; no sandbox, no automatic code generation or publication'}
    def save():
        report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    def remaining():
        return min(timeout, budget - (time.monotonic() - start))
    try:
        frozen = output / 'frozen'
        frozen.mkdir()
        shutil.copy2(__file__, frozen / 'driver.py')
        copy_tree(objectives, frozen / 'objectives')
        baseline = output / 'baseline'
        copy_tree(source, baseline)
        report['baseline_target_sha256'] = digest(baseline / TARGET)
        report['objective_sha256'] = {str(p.relative_to(frozen)): digest(p) for p in (frozen / 'objectives').rglob('*.py')}
        if remaining() <= 0:
            report['stop'] = 'total_budget'
            return report
        best = run_eval(frozen / 'driver.py', baseline, frozen / 'objectives', output, remaining())
        report['baseline'] = best
        if not eligible(best):
            report['stop'] = 'total_budget' if remaining() <= 0 else 'invalid_baseline_or_objectives'
            return report
        if failures(best['objective']) == 0:
            report['stop'] = 'objective_already_satisfied'
            return report
        stale = 0
        for index, (name, payload) in enumerate(payloads, 1):
            if remaining() <= 0:
                report['stop'] = 'total_budget'
                break
            folder = output / f'round-{index:02d}'
            folder.mkdir()
            tree = folder / 'candidate'
            copy_tree(baseline, tree)
            (tree / TARGET).write_bytes(payload)
            # Every candidate starts from immutable baseline, not previous side effects.
            result = run_eval(frozen / 'driver.py', tree, frozen / 'objectives', folder, max(.001, remaining()))
            improved = (eligible(result) and result['regression']['total'] == best['regression']['total']
                        and result['objective']['total'] == best['objective']['total']
                        and failures(result['objective']) < failures(best['objective']))
            row = {'round': index, 'input': name, 'sha256': hashlib.sha256(payload).hexdigest(),
                   'evaluation': result, 'decision': 'keep' if improved else 'discard'}
            report['rounds'].append(row)
            if improved:
                best, stale = result, 0
                # Retain the input bytes, not any runtime-mutated candidate output.
                (output / 'accepted-bidflow.py').write_bytes(payload)
                report['accepted'] = {'round': index, 'file': 'accepted-bidflow.py', 'sha256': row['sha256']}
            else:
                stale += 1
            save()
            if result.get('error') == 'evaluation_integrity_changed':
                report['stop'] = 'evaluation_integrity_changed'
                break
            if failures(best['objective']) == 0:
                report['stop'] = 'objective_satisfied'
                break
            if remaining() <= 0:
                report['stop'] = 'total_budget'
                break
            if stale >= patience:
                report['stop'] = 'no_improvement'
                break
        report['stop'] = report['stop'] or ('round_limit' if len(candidates) >= rounds else 'candidates_exhausted')
        return report
    except BaseException:
        report['stop'] = 'interrupted_or_error'
        raise
    finally:
        save()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--evaluate':
        evaluate(*(Path(p).resolve() for p in sys.argv[2:]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--objectives', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, action='append', default=[])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--patience', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--budget', type=float, default=600)
    args = parser.parse_args()
    print(json.dumps(loop(args.source, args.objectives, args.candidate, args.out, args.rounds,
                          args.patience, args.timeout, args.budget), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
