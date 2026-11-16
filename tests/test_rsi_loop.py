"""Independent synthetic tests for bounded candidate selection (no network/model)."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('rsi_loop', Path(__file__).resolve().parents[1] / 'tools/rsi_loop.py')
rsi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rsi)


@unittest.skipUnless(os.name == 'posix', 'POSIX-only process-group runner')
class LoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / rsi.TARGET).parent.mkdir(parents=True)
        (self.source / rsi.TARGET).write_text('VALUE = 0\nSAFE = True\n')
        (self.source / 'tests').mkdir()
        self.objectives = self.root / 'objectives'
        self.objectives.mkdir()
        load = "import importlib.util, os\nfrom pathlib import Path\nimport unittest\ns = importlib.util.spec_from_file_location('candidate', Path(os.environ['RSI_CANDIDATE_ROOT']) / '" + str(rsi.TARGET) + "')\nm = importlib.util.module_from_spec(s)\ns.loader.exec_module(m)\n"
        (self.source / 'tests/test_guard.py').write_text(load + 'class Guard(unittest.TestCase):\n def test_safe(self): self.assertTrue(m.SAFE)\n')
        (self.objectives / 'test_objective.py').write_text(load + 'class Objective(unittest.TestCase):\n def test_one(self): self.assertGreaterEqual(m.VALUE, 1)\n def test_two(self): self.assertGreaterEqual(m.VALUE, 2)\n')

    def candidate(self, value, safe=True, extra=''):
        path = self.root / f'candidate-{value}-{safe}.py'
        path.write_text(f'VALUE = {value}\nSAFE = {safe}\n' + extra)
        return path

    def run_loop(self, candidates, **kw):
        return rsi.loop(self.source, self.objectives, candidates, self.root / 'result', **kw)

    def test_improve_then_reject_then_finish_without_changing_source(self):
        before = (self.source / rsi.TARGET).read_bytes()
        result = self.run_loop([self.candidate(1), self.candidate(2, False), self.candidate(2)])
        self.assertEqual([r['decision'] for r in result['rounds']], ['keep', 'discard', 'keep'])
        self.assertEqual(result['accepted']['round'], 3)
        self.assertEqual(result['stop'], 'objective_satisfied')
        self.assertEqual((self.source / rsi.TARGET).read_bytes(), before)
        self.assertEqual(json.loads((self.root / 'result/report.json').read_text())['stop'], 'objective_satisfied')

    def test_patience_retains_last_good_candidate(self):
        result = self.run_loop([self.candidate(1), self.candidate(0), self.candidate(-1)])
        self.assertEqual(result['stop'], 'no_improvement')
        self.assertEqual(result['accepted']['round'], 1)

    def test_round_budget(self):
        result = self.run_loop([self.candidate(1), self.candidate(2)], rounds=1, patience=1)
        self.assertEqual(len(result['rounds']), 1)
        self.assertEqual(result['stop'], 'round_limit')

    def test_timeout_discard(self):
        result = self.run_loop([self.candidate(1, extra='import time\ntime.sleep(10)\n')], timeout=.4)
        self.assertEqual(result['rounds'][0]['evaluation']['error'], 'timeout')
        self.assertIsNone(result['accepted'])

    def test_bad_baseline_stops_before_candidates(self):
        (self.source / rsi.TARGET).write_text('VALUE=0\nSAFE=False\n')
        result = self.run_loop([self.candidate(2)])
        self.assertEqual(result['stop'], 'invalid_baseline_or_objectives')
        self.assertEqual(result['rounds'], [])

    def test_symlink_rejected(self):
        (self.source / 'leak').symlink_to('/tmp')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.run_loop([])

    def test_existing_destination_rejected(self):
        (self.root / 'result').mkdir()
        with self.assertRaisesRegex(ValueError, 'must not exist'):
            self.run_loop([])

    def test_in_tree_output_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            rsi.loop(self.source, self.objectives, [], self.source / 'results')

    def test_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            self.run_loop([], rounds=0)
        with self.assertRaises(ValueError):
            self.run_loop([], timeout=float('nan'))

    def test_objective_already_passes(self):
        (self.source / rsi.TARGET).write_text('VALUE=2\nSAFE=True\n')
        self.assertEqual(self.run_loop([])['stop'], 'objective_already_satisfied')

    def test_evaluator_modification_rejected(self):
        code = "from pathlib import Path\nimport os\np = Path(os.environ['RSI_CANDIDATE_ROOT']) / 'tests/test_guard.py'\np.write_text(p.read_text() + '\\n# changed\\n')\n"
        result = self.run_loop([self.candidate(2, extra=code)])
        self.assertEqual(result['rounds'][0]['evaluation']['error'], 'evaluation_integrity_changed')
        self.assertEqual(result['stop'], 'evaluation_integrity_changed')
        self.assertIsNone(result['accepted'])

    def test_total_budget_stops_baseline(self):
        (self.source / rsi.TARGET).write_text('import time\ntime.sleep(10)\nVALUE=0\nSAFE=True\n')
        result = self.run_loop([self.candidate(2)], budget=.2)
        self.assertEqual(result['stop'], 'total_budget')
        self.assertEqual(result['rounds'], [])

    def test_missing_objectives_rejected(self):
        (self.objectives / 'test_objective.py').unlink()
        with self.assertRaisesRegex(ValueError, 'independent objective'):
            self.run_loop([])

    def test_symlink_candidate_rejected(self):
        link = self.root / 'linked.py'
        link.symlink_to(self.candidate(2))
        with self.assertRaisesRegex(ValueError, 'regular local file'):
            self.run_loop([link])

    def test_output_within_objectives_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            rsi.loop(self.source, self.objectives, [], self.objectives / 'results')

    def test_timeout_cannot_poison_next_objective_baseline(self):
        code = "from pathlib import Path\nimport os, time\np = Path(os.environ['RSI_CANDIDATE_ROOT']).parent.parent / 'frozen/objectives/test_objective.py'\np.write_text(p.read_text().replace('m.VALUE, 1', 'm.VALUE, 0').replace('m.VALUE, 2', 'm.VALUE, 0'))\ntime.sleep(10)\n"
        result = self.run_loop([self.candidate(1, extra=code), self.candidate(0)], timeout=.4)
        self.assertEqual(result['stop'], 'evaluation_integrity_changed')
        self.assertEqual(len(result['rounds']), 1)
        self.assertIsNone(result['accepted'])

    def test_non_python_fixture_poisoning_stops_before_next_round(self):
        fixture = self.objectives / 'expected.json'
        fixture.write_text('{"minimum": 2}')
        code = "from pathlib import Path\nimport os\np = Path(os.environ['RSI_CANDIDATE_ROOT']).parent.parent / 'frozen/objectives/expected.json'\np.write_text('{\"minimum\": 0}')\n"
        result = self.run_loop([self.candidate(1, extra=code), self.candidate(2)])
        self.assertEqual(result['stop'], 'evaluation_integrity_changed')
        self.assertEqual(len(result['rounds']), 1)
        self.assertIsNone(result['accepted'])

    def test_external_to_tests_csv_dependency_changes_rejected(self):
        fixture = self.source / 'fixtures' / 'rows.csv'
        fixture.parent.mkdir()
        fixture.write_text('expected\n2\n')
        code = "from pathlib import Path\nimport os\np = Path(os.environ['RSI_CANDIDATE_ROOT']) / 'fixtures/rows.csv'\np.write_text('expected\\n0\\n')\n"
        result = self.run_loop([self.candidate(2, extra=code)])
        self.assertEqual(result['stop'], 'evaluation_integrity_changed')
        self.assertIsNone(result['accepted'])

    def test_fixture_addition_deletion_and_symlink_rejected(self):
        for operation in ('add', 'delete', 'symlink'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as out:
                fixture = self.objectives / 'expected.json'
                fixture.write_text('{}')
                prefix = "from pathlib import Path\nimport os\np = Path(os.environ['RSI_CANDIDATE_ROOT']).parent.parent / 'frozen/objectives/expected.json'\n"
                action = {'add': "p.with_name('new.csv').write_text('x')\n",
                          'delete': "p.unlink()\n",
                          'symlink': "p.unlink(); p.symlink_to('/dev/null')\n"}[operation]
                result = rsi.loop(self.source, self.objectives, [self.candidate(2, extra=prefix + action)], Path(out) / 'result')
                self.assertEqual(result['stop'], 'evaluation_integrity_changed')
                self.assertIsNone(result['accepted'])

    def test_normal_exit_cleans_child_processes(self):
        import signal
        import time
        pidfile = self.root / 'child-pids'
        code = "import subprocess, sys\nfrom pathlib import Path\np = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\nwith Path(" + repr(str(pidfile)) + ").open('a') as f: f.write(str(p.pid) + '\\n')\n"
        try:
            result = self.run_loop([self.candidate(2, extra=code)])
            self.assertEqual(result['stop'], 'objective_satisfied')
            pids = [int(p) for p in pidfile.read_text().splitlines()]
            self.assertTrue(pids)
            time.sleep(.05)
            for pid in pids:
                status = Path(f'/proc/{pid}/stat')
                if status.exists():
                    self.assertEqual(status.read_text().split()[2], 'Z', f'Child {pid} still running')
        finally:
            if pidfile.exists():
                for pid in map(int, pidfile.read_text().splitlines()):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_interruption_also_cleans_process_group(self):
        import signal
        import time
        from unittest import mock
        # A trusted evaluator starts a child; interrupt the caller's wait.
        folder = self.root / 'interrupt'
        folder.mkdir()
        marker = folder / 'started'
        driver = folder / 'driver.py'
        driver.write_text("import subprocess, sys, time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\nPath(" + repr(str(marker)) + ").write_text(str(p.pid))\ntime.sleep(30)\n")
        original_popen = rsi.subprocess.Popen
        processes = []
        def start(*args, **kwargs):
            proc = original_popen(*args, **kwargs)
            processes.append(proc)
            original_wait = proc.wait
            interrupted = False
            def wait(*args, **kwargs):
                nonlocal interrupted
                if not interrupted:
                    interrupted = True
                    deadline = time.monotonic() + 2
                    while not marker.exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    raise KeyboardInterrupt()
                return original_wait(*args, **kwargs)
            proc.wait = wait
            return proc
        try:
            with mock.patch.object(rsi.subprocess, 'Popen', side_effect=start):
                with self.assertRaises(KeyboardInterrupt):
                    rsi.run_eval(driver, self.source, self.objectives, folder, 5)
            self.assertTrue(marker.exists())
            self.assertIsNotNone(processes[0].poll(), 'Evaluator survived interruption')
            time.sleep(.05)
            child_status = Path('/proc') / marker.read_text() / 'stat'
            if child_status.exists():
                self.assertEqual(child_status.read_text().split()[2], 'Z')
        finally:
            for proc in processes:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
