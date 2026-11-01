"""Exercise packaging and escalation without a local inference server."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import orchestrator
import runner
import test_runner


class PackagingTests(unittest.TestCase):
    def cli(self, data, *args, code=0):
        result = subprocess.run([sys.executable, str(runner.ROOT / 'orchestrator.py'), *map(str, args)],
                                env={**os.environ, 'AI_ORCHESTRATOR_HOME': str(data)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def fixture(self, temp):
        obj = test_runner.RunnerTests().make_trial_runner(temp, 4, 1)
        data = Path(temp) / 'data'
        config = dict(obj.config, guide=str(runner.ROOT / 'configs/entourage-guide.md'),
                      claude=sys.executable, dispute_escalation=True, invocation_timeout_seconds=10)
        profiles = data / 'profiles'
        profiles.mkdir(parents=True)
        orchestrator.write(profiles / 'trial.json', config)
        task = Path(temp) / 'task.json'
        orchestrator.write(task, dict(obj.task, problem='Implement correct behavior'))
        return obj, data, task

    def test_doctor_uses_committed_worktree_and_preserves_dirty_source(self):
        with tempfile.TemporaryDirectory() as temp:
            obj, data, task = self.fixture(temp)
            (obj.repo / 'code.txt').write_text('unrelated dirty change')
            (obj.repo / 'private-untracked.txt').write_text('keep')
            result = json.loads(self.cli(data, 'doctor', 'trial').stdout.split('\n', 2)[-1])
            self.assertEqual(result['status'], 'ready')
            self.assertEqual((Path(result['worktree']) / 'code.txt').read_text(), 'baseline')
            self.assertEqual((obj.repo / 'code.txt').read_text(), 'unrelated dirty change')
            self.assertEqual((obj.repo / 'private-untracked.txt').read_text(), 'keep')
            self.assertFalse((Path(result['run']) / 'artifacts/invocations.jsonl').exists())

    def fake_cli(self, temp):
        cli = Path(temp) / 'fake-claude'
        cli.write_text('#!' + sys.executable + '\n' + '''import json, sys
from pathlib import Path
text = sys.stdin.read()
if text.startswith('You implement'):
    Path('code.txt').write_text('fixed')
    result = 'Implemented; checks are owned by runner.'
else:
    result = json.dumps({'verdict':'approve','findings':[], 'summary':'checked',
        'coverage':[{'criterion':1,'reason':'fixed source inspected','evidence':[{'anchor':'S1:1'}]}]})
print(json.dumps({'type':'result','result':result,'is_error':False}))
''')
        cli.chmod(0o755)
        return cli

    def test_cli_run_end_to_end_accepts_exact_patch_without_touching_source(self):
        with tempfile.TemporaryDirectory() as temp:
            obj, data, task = self.fixture(temp)
            path = data / 'profiles/trial.json'
            config = orchestrator.read(path)
            config['claude'] = str(self.fake_cli(temp))
            orchestrator.write(path, config)
            result = self.cli(data, 'run', 'trial', '--task', task)
            summary = json.loads(result.stdout.split('\n', 1)[1])
            self.assertEqual(summary['status'], 'accepted')
            self.assertIn(b'+fixed', Path(summary['patch']).read_bytes())
            self.assertEqual((obj.repo / 'code.txt').read_text(), 'baseline')
            self.assertEqual(runner.git(obj.repo, 'status', '--porcelain'), b'')
            state = json.loads(self.cli(data, 'status', summary['run']).stdout)
            self.assertEqual(state['patch_sha256'], runner.digest(Path(summary['patch']).read_bytes()))

    def test_cli_escalation_and_resume_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp:
            obj, data, task = self.fixture(temp)
            cli = self.fake_cli(temp)
            content = cli.read_text().replace("print(json.dumps({'type':'result'", """if not text.startswith('You implement'):
    review = json.loads(result)
    review.update(verdict='request_changes', findings=[{'id':'R1','file':'code.txt',
        'issue':'alleged defect','requested_change':'fix','failure_case':'fixed allegedly wrong',
        'evidence':[{'anchor':'S1:1'}]}])
    if text.startswith('You are the FRESH'):
        review['resolutions'] = [{'id':'R1','decision':'upheld','reason':'still alleged'}]
    result = json.dumps(review)
print(json.dumps({'type':'result'""")
            cli.write_text(content)
            profile = data / 'profiles/trial.json'
            config = orchestrator.read(profile)
            config['claude'] = str(cli)
            orchestrator.write(profile, config)
            output = self.cli(data, 'run', 'trial', '--task', task, code=2)
            summary = json.loads(output.stdout.split('\n', 1)[1])
            self.assertEqual(summary['status'], 'parent_required')
            decision = Path(temp) / 'decision.json'
            orchestrator.write(decision, {'author':'hosted_parent', 'resolutions':[
                {'id':'R1','decision':'withdrawn','reason':'fixed source and gates verified'}]})
            resumed = json.loads(self.cli(data, 'resume', summary['run'], '--decision', decision).stdout)
            self.assertEqual(resumed['status'], 'accepted')
            self.assertTrue(Path(resumed['patch']).is_file())
            self.assertEqual((obj.repo / 'code.txt').read_text(), 'baseline')

    def test_queue_continues_after_failure_from_same_base(self):
        with tempfile.TemporaryDirectory() as temp:
            obj, data, task = self.fixture(temp)
            path = data / 'profiles/trial.json'
            config = orchestrator.read(path)
            config['claude'] = str(self.fake_cli(temp))
            orchestrator.write(path, config)
            # First task cannot satisfy this required deliverable; second can succeed.
            bad = dict(orchestrator.read(task), id='bad', allowed_files=['code.txt', 'missing.txt'],
                       required_changed_files=['missing.txt'])
            bad_path = Path(temp) / 'bad.json'
            orchestrator.write(bad_path, bad)
            summary = json.loads(self.cli(data, 'queue', 'trial', '--task', bad_path, '--task', task, code=1).stdout)
            results = summary['results']
            self.assertEqual([r['status'] for r in results], ['unresolved', 'accepted'])
            self.assertEqual(results[0]['base_commit'], results[1]['base_commit'])
            self.assertNotEqual(results[0]['worktree'], results[1]['worktree'])

    def test_validation_rejects_empty_gates_scope_escape_and_missing_deliverables(self):
        with tempfile.TemporaryDirectory() as temp:
            obj, _, _ = self.fixture(temp)
            task = dict(obj.task, problem='change')
            for bad in (dict(obj.config, checks=[]), dict(obj.config, min_review_rounds=5),
                        dict(obj.config, checks=[{'name':'../bad','cwd':'.','argv':['true'] }])):
                with self.assertRaises(ValueError):
                    orchestrator.validate(dict(bad, invocation_timeout_seconds=10), task)
            for change in ({'allowed_files':['../secret']}, {'allowed_files':['.git/config']},
                           {'required_changed_files':['outside']}, {'acceptance_criteria':[]}):
                with self.assertRaises(ValueError):
                    orchestrator.validate(dict(obj.config, invocation_timeout_seconds=10), dict(task, **change))

    def test_install_is_idempotent_and_runs_from_skill_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for _ in range(2):
                self.cli(root / 'data', 'install', '--codex-home', root / 'codex', '--bin-dir', root / 'bin')
            subprocess.run([str(root / 'bin/ai-orchestrator'), '--help'], check=True, capture_output=True)
            subprocess.run([sys.executable, str(root / 'codex/skills/local-coding-loop/scripts/orchestrator.py'), '--help'],
                           check=True, capture_output=True)
            (root / 'bin/ai-orchestrator').write_text('unrelated')
            self.cli(root / 'data', 'install', '--codex-home', root / 'codex', '--bin-dir', root / 'bin', code=1)
            self.assertEqual((root / 'bin/ai-orchestrator').read_text(), 'unrelated')


class IntegratedDisputeTests(unittest.TestCase):
    def fixture(self, temp, adjudication='upheld'):
        obj = test_runner.RunnerTests().make_trial_runner(temp, 4, 1)
        obj.config['dispute_escalation'] = True
        calls = []
        def invoke(persona, number, extra):
            calls.append(persona)
            if persona == 'implementer':
                (obj.repo / 'code.txt').write_text('fixed')
                return 'R1 rejected: fixed source proves this is a false premise'
            review = json.loads(test_runner.RunnerTests().approval(obj))
            finding = {'id':'R1', 'file':'code.txt', 'issue':'alleged failure',
                       'requested_change':'repair', 'failure_case':'fixed allegedly incorrect',
                       'evidence':[{'anchor':'S1:1'}]}
            if persona == 'reviewer' or adjudication != 'withdrawn':
                review.update(verdict='request_changes', findings=[finding])
            if persona == 'adjudicator':
                review['resolutions'] = [{'id':'R1', 'decision':adjudication, 'reason':'source inspected'}]
            return json.dumps(review)
        obj.invoke = invoke
        return obj, calls

    def decision(self, choice='withdrawn'):
        return {'author':'hosted_parent', 'resolutions':[{'id':'R1','decision':choice,'reason':'counterexample verified'}]}

    def test_fresh_opinion_resolves_false_objection_without_parent(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            obj, calls = self.fixture(temp, 'withdrawn')
            self.assertEqual(obj.execute(), 0)
            self.assertEqual(calls, ['implementer','reviewer','implementer','reviewer','adjudicator'])
            self.assertTrue((obj.directory / 'accepted.patch').exists())

    def test_checkpoint_resumes_in_fresh_runner_and_reruns_final_checks(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            obj, calls = self.fixture(temp)
            self.assertEqual(obj.execute(), 2)
            self.assertFalse((obj.directory / 'accepted.patch').exists())
            fresh = runner.Runner(obj.config, obj.task, obj.directory)
            with patch.object(fresh, 'invoke') as model:
                self.assertEqual(fresh.execute(self.decision()), 0)
                model.assert_not_called()
            self.assertTrue((obj.directory / 'final-checks.json').exists())
            self.assertEqual(json.loads((obj.directory / 'state.json').read_text())['status'], 'accepted')

    def test_parent_cannot_accept_changed_source_or_waive_final_failure(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            obj, _ = self.fixture(temp)
            self.assertEqual(obj.execute(), 2)
            (obj.repo / 'code.txt').write_text('changed behind parent')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                runner.Runner(obj.config, obj.task, obj.directory).execute(self.decision())
            (obj.repo / 'code.txt').write_text('fixed')
            fresh = runner.Runner(obj.config, obj.task, obj.directory)
            with patch.object(fresh, 'checks', return_value=(False, [])):
                with self.assertRaisesRegex(RuntimeError, 'Final checks failed'):
                    fresh.execute(self.decision())
            self.assertFalse((obj.directory / 'accepted.patch').exists())

    def test_resume_keeps_scope_guard_and_remaining_round_bound(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            obj, calls = self.fixture(temp)
            self.assertEqual(obj.execute(), 2)
            fresh = runner.Runner(obj.config, obj.task, obj.directory)
            rounds = []
            def implement(persona, number, extra):
                rounds.append(number)
                (fresh.repo / 'unrelated.txt').write_text('oops')
                fresh.guard()
            fresh.invoke = implement
            with self.assertRaisesRegex(RuntimeError, 'Out-of-scope'):
                fresh.execute(self.decision('upheld'))
            self.assertEqual(rounds, [3])
            self.assertFalse((fresh.directory / 'accepted.patch').exists())

    def test_acceptance_rechecks_required_deliverables_after_escalation(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            obj, _ = self.fixture(temp)
            self.assertEqual(obj.execute(), 2)
            # Acceptance must enforce the task independently of review/parent prose.
            obj.task['required_changed_files'] = ['missing.txt']
            with self.assertRaisesRegex(RuntimeError, 'deliverables missing'):
                obj.accept(2, 2, runner.snapshot(obj.repo), runner.patch(obj.repo))
            self.assertFalse((obj.directory / 'accepted.patch').exists())

    def test_changed_contract_or_controls_block_resume(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            obj, _ = self.fixture(temp)
            self.assertEqual(obj.execute(), 2)
            modified = dict(obj.config, max_rounds=99)
            with self.assertRaisesRegex(ValueError, 'contract changed'):
                runner.Runner(modified, obj.task, obj.directory).execute(self.decision())
            checkpoint = json.loads((obj.directory / 'checkpoint.json').read_text())
            checkpoint['controls'][str(runner.ROOT / 'runner.py')] = 'different'
            orchestrator.write(obj.directory / 'checkpoint.json', checkpoint)
            with self.assertRaisesRegex(RuntimeError, 'controls changed'):
                runner.Runner(obj.config, obj.task, obj.directory).execute(self.decision())

    def test_invalid_review_escalates_without_counting_an_approval(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            obj, _ = self.fixture(temp)
            original = obj.invoke
            obj.invoke = lambda role, n, extra: original(role, n, extra) if role == 'implementer' else 'malformed'
            self.assertEqual(obj.execute(), 2)
            self.assertEqual(json.loads((obj.directory / 'checkpoint.json').read_text())['reviews'], 0)
            self.assertFalse((obj.directory / 'accepted.patch').exists())


if __name__ == '__main__':
    unittest.main()
