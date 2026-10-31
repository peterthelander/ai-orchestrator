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
            task = {'id': 'T', 'title': 'test', 'allowed_files': ['source.txt']}
            obj = runner.Runner(config, task, artifacts)
            invocations = []

            def invoke(persona, round_number, extra):
                invocations.append((persona, round_number))
                if persona == 'implementer':
                    if round_number == 2:
                        self.assertIn('R1', obj.dialogue.read_text())
                    (repo / 'source.txt').write_text('draft' if round_number == 1 else 'fixed')
                    return 'implemented'
                review = {'verdict': 'request_changes' if round_number == 1 else 'approve',
                          'summary': 'review', 'findings': []}
                if round_number == 1:
                    review['findings'] = [{'id': 'R1', 'file': 'source.txt',
                                          'issue': 'draft needs correction', 'requested_change': 'fix'}]
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


if __name__ == '__main__':
    unittest.main()
