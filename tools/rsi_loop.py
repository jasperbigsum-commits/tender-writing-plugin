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
import tempfile
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


def evaluation_hashes(driver, root, objectives):
    """Freeze every copied dependency, not just test Python source.

    Fixtures may live outside tests/. Only the candidate target is excluded.
    Bytecode writes are disabled; tests must write scratch data to
    TMPDIR, never into these fixed trees. This is integrity checking, not a sandbox.
    """
    hashes = {'driver': digest(driver)}
    for label, directory in [('objective', objectives), ('baseline', root)]:
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError('Fixed dependency tree missing or replaced')
        for current, dirs, files in os.walk(directory, followlinks=False):
            for name in dirs + files:
                path = Path(current) / name
                relative = path.relative_to(directory)
                key = label + '/' + relative.as_posix()
                # Never follow a link, even when named like an ignored cache.
                if path.is_symlink():
                    raise ValueError('Fixed dependency became a symlink')
                if label == 'baseline' and relative == TARGET:
                    continue
                if path.is_dir():
                    hashes[key + '/'] = 'directory'
                elif path.is_file():
                    hashes[key] = digest(path)
                else:
                    raise ValueError('Fixed dependency is not a regular file')
    return hashes


def run_eval(driver, root, objectives, folder, timeout, expected_hashes=None):
    # The loop supplies ONE fingerprint frozen before baseline evaluation.
    if expected_hashes is None:
        expected_hashes = evaluation_hashes(driver, root, objectives)
    def intact():
        try:
            return evaluation_hashes(driver, root, objectives) == expected_hashes
        except (OSError, ValueError):
            return False
    if not intact():
        return {'error': 'evaluation_integrity_changed'}
    result = folder / 'evaluation.json'
    # No API keys, tokens, proxies, PYTHONPATH or user startup settings inherited.
    env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT') if key in os.environ}
    env.update(RSI_CANDIDATE_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1")
    timed_out = False
    with tempfile.TemporaryDirectory(prefix='evaluation-scratch-', dir=folder) as scratch, (folder / 'evaluation.log').open('wb') as log:
        env.update(HOME=scratch, TMPDIR=scratch)
        proc = subprocess.Popen([sys.executable, '-I', '-B', str(driver), '--evaluate', str(root), str(objectives), str(result)],
                                cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            # Also reap background descendants on success and caller interruption.
            # Processes that deliberately detach require a real OS sandbox.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                proc.wait()
    # Integrity takes priority even on timeout: never reuse a polluted evaluator.
    if not intact():
        return {'error': 'evaluation_integrity_changed'}
    if timed_out:
        return {'error': 'timeout'}
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
        expected_hashes = evaluation_hashes(frozen / 'driver.py', baseline, frozen / 'objectives')
        report['evaluation_sha256'] = expected_hashes
        report['baseline_target_sha256'] = digest(baseline / TARGET)
        report['objective_sha256'] = {str(p.relative_to(frozen)): digest(p) for p in (frozen / 'objectives').rglob('*') if p.is_file()}
        if remaining() <= 0:
            report['stop'] = 'total_budget'
            return report
        best = run_eval(frozen / 'driver.py', baseline, frozen / 'objectives', output, remaining(), expected_hashes)
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
            result = run_eval(frozen / 'driver.py', tree, frozen / 'objectives', folder, max(.001, remaining()), expected_hashes)
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
