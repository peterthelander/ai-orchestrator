import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import runner


class RunnerTests(unittest.TestCase):
    def test_result_parser_tolerates_cli_warning_but_requires_result(self):
        self.assertEqual(runner.parse_envelope('warning\n{"type":"result","result":"ok"}\n')['result'], 'ok')
        with self.assertRaises(ValueError):
            runner.parse_envelope('{"type":"warning"}')

    def test_review_rejects_false_approval_and_malformed_findings(self):
        for review in [
            {'verdict': 'approve', 'findings': [{'id': 'R1'}], 'summary': 'ok'},
            {'verdict': 'request_changes', 'findings': [], 'summary': 'bad'},
            {'verdict': 'approve', 'findings': [], 'summary': None},
        ]:
            with self.assertRaises(ValueError):
                runner.parse_review(json.dumps(review))
        self.assertEqual(runner.parse_review('{"verdict":"approve","findings":[],"summary":"ok"}')['verdict'], 'approve')

    def test_snapshot_detects_untracked_changes_and_deletions(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(['git', 'init', '-q', temp], check=True)
            file = repo / 'new.txt'
            before = runner.snapshot(repo)
            file.write_text('one')
            after = runner.snapshot(repo)
            self.assertEqual(runner.changed(before, after), {'new.txt'})
            file.write_text('two')
            self.assertEqual(runner.changed(after, runner.snapshot(repo)), {'new.txt'})
            file.unlink()
            self.assertEqual(runner.changed(after, runner.snapshot(repo)), {'new.txt'})

    def test_failed_checks_never_accept_and_round_limit_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            obj = object.__new__(runner.Runner)
            obj.repo = Path(temp)
            obj.directory = Path(temp)
            obj.base = {}
            obj.config = {'max_rounds': 2, 'min_review_rounds': 1}
            obj.task = {'id': 'T'}
            states = []
            obj.state = lambda status, **kw: states.append(status)
            obj.append = lambda *args: None
            obj.guard = lambda: None
            obj.invoke = lambda *args: 'implementation'
            check = {'log': 'failed.log', 'exit_code': 1}
            with patch.object(runner, 'git', return_value=b''), patch.object(runner, 'snapshot', return_value={'a': 'b'}), \
                 patch.object(runner, 'patch', return_value=b'diff'), \
                 patch.object(obj, 'checks', side_effect=[(True, []), (False, [check]), (False, [check])]):
                self.assertEqual(obj.execute(), 1)
            self.assertEqual(states[-1], 'unresolved')
            self.assertNotIn('accepted', states)

    def test_baseline_failure_prevents_model_invocation(self):
        with tempfile.TemporaryDirectory() as temp:
            obj = object.__new__(runner.Runner)
            obj.repo = Path(temp)
            obj.state = lambda *args, **kw: None
            with patch.object(runner, 'git', return_value=b''), \
                 patch.object(obj, 'checks', return_value=(False, [])), \
                 patch.object(obj, 'invoke') as invoke:
                self.assertEqual(obj.execute(), 1)
                invoke.assert_not_called()

    def test_review_repair_cycle_accepts_only_final_verified_patch(self):
        import contextlib
        import io
        import sys
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / 'source.txt').write_text('baseline')
            subprocess.run(['git', '-C', str(repo), 'add', 'source.txt'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c',
                            'user.email=test@example.invalid', 'commit', '-qm', 'baseline'], check=True)
            artifacts = Path(temp) / 'artifacts'
            artifacts.mkdir()
            config = {'repository': str(repo), 'node_bin': '/usr/bin',
                      'guide': 'configs/entourage-guide.md', 'max_rounds': 2,
                      'min_review_rounds': 1, 'check_timeout_seconds': 10,
                      'checks': [{'name': 'check', 'cwd': '.', 'argv': [sys.executable, '-c',
                        "from pathlib import Path; assert Path('source.txt').read_text() in ('baseline','draft','fixed')"]}]}
            task = {'id': 'T', 'title': 'test', 'allowed_files': ['source.txt'], 'acceptance_criteria': ['correct behavior']}
            obj = runner.Runner(config, task, artifacts)
            invocations = []

            def invoke(persona, round_number, extra):
                invocations.append((persona, round_number))
                if persona == 'implementer':
                    if round_number == 2:
                        self.assertIn('R1', obj.dialogue.read_text())
                    (repo / 'source.txt').write_text('draft' if round_number == 1 else 'fixed')
                    return 'implemented'
                evidence = [{'file': 'source.txt', 'line': 1, 'quote': (repo / 'source.txt').read_text()}]
                review = {'verdict': 'request_changes' if round_number == 1 else 'approve',
                          'summary': 'review', 'findings': [],
                          'coverage': [{'criterion': 1, 'reason': 'inspected', 'evidence': evidence}]}
                if round_number == 1:
                    review['findings'] = [{'id': 'R1', 'file': 'source.txt',
                                          'issue': 'draft needs correction', 'requested_change': 'fix',
                                          'failure_case': 'draft expected fixed', 'evidence': evidence}]
                return json.dumps(review)

            obj.invoke = invoke
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(obj.execute(), 0)
            state = json.loads((artifacts / 'state.json').read_text())
            self.assertEqual(state['status'], 'accepted')
            self.assertEqual(state['round'], 2)
            self.assertEqual(state['patch_sha256'], runner.digest((artifacts / 'accepted.patch').read_bytes()))
            self.assertIn(b'+fixed', (artifacts / 'accepted.patch').read_bytes())
            self.assertEqual(invocations, [('implementer', 1), ('reviewer', 1),
                                           ('implementer', 2), ('reviewer', 2)])



    def test_evidence_requires_current_lines_and_complete_coverage(self):
        import copy
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / 'source.py').write_text('first\nactual replay\n')
            task = {'allowed_files': ['source.py'], 'acceptance_criteria': ['one']}
            valid = {'findings': [], 'coverage': [{'criterion': 1, 'reason': 'inspected',
                     'evidence': [{'file': 'source.py', 'line': 2, 'quote': 'actual replay'}]}]}
            runner.validate_review_evidence(valid, repo, task)
            for field, value in [('file', '../outside'), ('quote', 'invented'), ('quote', '')]:
                bad = copy.deepcopy(valid)
                bad['coverage'][0]['evidence'][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    runner.validate_review_evidence(bad, repo, task)
            for coverage in ([], valid['coverage'] * 2):
                bad = copy.deepcopy(valid)
                bad['coverage'] = coverage
                with self.assertRaises(ValueError):
                    runner.validate_review_evidence(bad, repo, task)
            bad = copy.deepcopy(valid)
            bad['findings'] = [{'evidence': valid['coverage'][0]['evidence']}]
            with self.assertRaises(ValueError):
                runner.validate_review_evidence(bad, repo, task)

    def test_review_context_has_full_source_without_prior_approval_narratives(self):
        with tempfile.TemporaryDirectory() as temp:
            obj = object.__new__(runner.Runner)
            obj.repo = Path(temp)
            (obj.repo / 'code.py').write_text('unchanged replay\nchanged message\n')
            obj.task = {'allowed_files': ['code.py']}
            obj.config = {}
            obj.latest_review = {'findings': [], 'verdict': 'approve', 'summary': 'UNTRUSTED PRIOR CLAIM'}
            obj.latest_checks = []
            text = obj.context('reviewer')
            self.assertIn('[S1:1] 1: unchanged replay', text)
            self.assertIn('2: changed message', text)
            self.assertNotIn('UNTRUSTED PRIOR CLAIM', text)
            self.assertNotIn('approve', text)
            obj.config['max_review_source_bytes'] = 1
            with self.assertRaises(ValueError):
                obj.context('reviewer')

    def make_trial_runner(self, temp, max_rounds, min_reviews):
        import sys
        repo = Path(temp) / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        (repo / 'code.txt').write_text('baseline')
        subprocess.run(['git', '-C', str(repo), 'add', 'code.txt'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c',
                        'user.email=test@example.invalid', 'commit', '-qm', 'baseline'], check=True)
        artifacts = Path(temp) / 'artifacts'
        artifacts.mkdir()
        config = {'repository': str(repo), 'node_bin': '/usr/bin', 'guide': 'configs/entourage-guide.md',
                  'max_rounds': max_rounds, 'min_review_rounds': min_reviews, 'check_timeout_seconds': 10,
                  'checks': [{'name': 'check', 'cwd': '.', 'argv': [sys.executable, '-c',
                    "from pathlib import Path; assert Path('code.txt').read_text() != 'bad'"]}]}
        task = {'id': 'T', 'title': 'trial', 'allowed_files': ['code.txt'], 'acceptance_criteria': ['correct']}
        return runner.Runner(config, task, artifacts)

    def approval(self, obj, quote=None):
        return json.dumps({'verdict': 'approve', 'findings': [], 'summary': 'inspected',
                           'coverage': [{'criterion': 1, 'reason': 'checked', 'evidence': [
                               {'file': 'code.txt', 'line': 1,
                                'quote': quote or (obj.repo / 'code.txt').read_text()}]}]})

    def test_failed_implementation_round_does_not_count_as_a_review(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as temp:
            obj = self.make_trial_runner(temp, max_rounds=3, min_reviews=2)
            reviews = []
            def invoke(persona, number, extra):
                if persona == 'implementer':
                    (obj.repo / 'code.txt').write_text('bad' if number == 1 else 'fixed')
                    return 'implemented'
                reviews.append(number)
                return self.approval(obj)
            obj.invoke = invoke
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(obj.execute(), 0)
            self.assertEqual(reviews, [2, 3])
            self.assertEqual(json.loads((obj.directory / 'state.json').read_text())['reviews'], 2)

    def test_invalid_citations_retry_without_editing_or_counting_extra_review(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as temp:
            obj = self.make_trial_runner(temp, max_rounds=1, min_reviews=1)
            attempts = []
            def invoke(persona, number, extra):
                if persona == 'implementer':
                    (obj.repo / 'code.txt').write_text('fixed')
                    return 'implemented'
                attempts.append(obj.review_attempt)
                if obj.review_attempt == 2:
                    self.assertIn('OUTPUT VALIDATION ERROR', extra)
                return self.approval(obj, 'invented' if obj.review_attempt == 1 else None)
            obj.invoke = invoke
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(obj.execute(), 0)
            self.assertEqual(attempts, [1, 2])
            self.assertEqual(json.loads((obj.directory / 'state.json').read_text())['reviews'], 1)



    def test_quote_resolution_preserves_input_and_ignores_model_line_arithmetic(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / 'code.py').write_text('header\nunique body replay\n')
            task = {'allowed_files': ['code.py'], 'acceptance_criteria': ['one']}
            review = {'findings': [], 'coverage': [{'criterion': 1, 'reason': 'checked',
                      'evidence': [{'file': 'code.py', 'line': 99, 'quote': 'unique body replay'}]}]}
            result = runner.validate_review_evidence(review, repo, task)
            evidence = result['coverage'][0]['evidence'][0]
            self.assertEqual(evidence['line'], 2)
            self.assertEqual(evidence['model_line'], 99)
            self.assertEqual(review['coverage'][0]['evidence'][0]['line'], 99)
            del review['coverage'][0]['evidence'][0]['line']
            evidence = runner.validate_review_evidence(review, repo, task)['coverage'][0]['evidence'][0]
            self.assertEqual(evidence['line'], 2)
            self.assertNotIn('model_line', evidence)

    def test_quote_validation_aggregates_missing_ambiguous_and_coverage_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / 'code.py').write_text('repeated\nrepeated\n')
            task = {'allowed_files': ['code.py'], 'acceptance_criteria': ['one', 'two']}
            review = {'findings': [], 'coverage': [{'criterion': 'one', 'reason': '', 'evidence': [
                {'file': 'code.py', 'line': 1, 'quote': 'repeated'},
                {'file': 'code.py', 'quote': 'invented'}]}]}
            with self.assertRaises(ValueError) as failure:
                runner.validate_review_evidence(review, repo, task)
            for message in ['ambiguous quote', 'exact quote not found', 'unique integer',
                            'reasoning is required', 'Missing acceptance criteria: 1, 2']:
                self.assertIn(message, str(failure.exception))



    def test_source_ids_resolve_exact_code_without_ambiguous_quote_copying(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / 'code.py').write_text('same\n\nsame\n')
            task = {'allowed_files': ['code.py'], 'acceptance_criteria': ['one']}
            review = {'findings': [], 'coverage': [{'criterion': 1, 'reason': 'checked',
                      'evidence': [{'anchor': 'S1:3'}]}]}
            result = runner.validate_review_evidence(review, repo, task)
            evidence = result['coverage'][0]['evidence'][0]
            self.assertEqual(evidence, {'anchor': 'S1:3', 'file': 'code.py', 'line': 3, 'quote': 'same'})
            self.assertEqual(review['coverage'][0]['evidence'][0], {'anchor': 'S1:3'})
            for anchor in ('S1:2', 'S1:4', 'S2:1', 'S0:1', 'S1:0', 'S1:01', None):
                review['coverage'][0]['evidence'] = [{'anchor': anchor}]
                with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                    runner.validate_review_evidence(review, repo, task)
            for conflict in ({'file': 'other.py'}, {'quote': 'invented'}):
                review['coverage'][0]['evidence'] = [{'anchor': 'S1:1', **conflict}]
                with self.assertRaises(ValueError):
                    runner.validate_review_evidence(review, repo, task)



    def test_pending_review_gets_rebuttal_without_prior_verdict_narrative(self):
        with tempfile.TemporaryDirectory() as temp:
            obj = object.__new__(runner.Runner)
            obj.repo = Path(temp)
            (obj.repo / 'code.py').write_text('actual implementation\n')
            obj.task = {'allowed_files': ['code.py']}
            obj.config = {}
            obj.latest_checks = []
            obj.latest_implementation = 'R1 rejected: actual deterministic counterexample'
            obj.latest_review = {'findings': [{'id': 'R1', 'issue': 'alleged defect'}],
                                 'summary': 'PRIOR REVIEW NARRATIVE'}
            text = obj.context('reviewer')
            self.assertIn('R1 rejected: actual deterministic counterexample', text)
            self.assertIn('Unverified implementer response', text)
            self.assertNotIn('PRIOR REVIEW NARRATIVE', text)
            obj.latest_review = {'findings': []}
            self.assertNotIn('R1 rejected', obj.context('reviewer'))


if __name__ == '__main__':
    unittest.main()
