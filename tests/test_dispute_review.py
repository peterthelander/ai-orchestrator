import unittest
from dispute_review import resolutions


class DisputeResolutionTests(unittest.TestCase):
    def test_mixed_findings_resolve_independently(self):
        findings = [{'id': 'X'}, {'id': 'Y'}, {'id': 'Z'}]
        report = {'findings': [{'id': 'Y'}, {'id': 'Z'}], 'resolutions': [
            {'id': 'X', 'decision': 'withdrawn', 'reason': 'counterexample verified'},
            {'id': 'Y', 'decision': 'upheld', 'reason': 'failure reproduced'},
            {'id': 'Z', 'decision': 'uncertain', 'reason': 'needs further evidence'}]}
        self.assertEqual(set(resolutions(report, findings)), {'X', 'Y', 'Z'})

    def test_missing_duplicate_and_contradictory_decisions_fail(self):
        rows = [[], [{'id': 'R1', 'decision': 'withdrawn', 'reason': 'ok'}] * 2,
                [{'id': 'R1', 'decision': 'upheld', 'reason': 'ok'}],
                [{'id': 'R2', 'decision': 'withdrawn', 'reason': 'ok'}],
                [{'id': 'R1', 'decision': 'withdrawn', 'reason': ''}]]
        for resolutions_list in rows:
            with self.subTest(rows=resolutions_list), self.assertRaises(ValueError):
                resolutions({'findings': [], 'resolutions': resolutions_list}, [{'id': 'R1'}])

    def test_withdrawal_cannot_leave_finding_active(self):
        with self.assertRaises(ValueError):
            resolutions({'findings': [{'id': 'R1'}], 'resolutions': [
                {'id': 'R1', 'decision': 'withdrawn', 'reason': 'false premise'}]}, [{'id': 'R1'}])


class ParentDecisionTests(unittest.TestCase):
    def fixture(self, temp):
        import subprocess
        from pathlib import Path
        import json
        from runner import digest, patch, snapshot
        repo = Path(temp)
        subprocess.run(['git', 'init', '-q', temp], check=True)
        (repo / 'code.txt').write_text('baseline')
        subprocess.run(['git', '-C', temp, 'add', 'code.txt'], check=True)
        subprocess.run(['git', '-C', temp, '-c', 'user.name=Test', '-c',
                        'user.email=test@example.invalid', 'commit', '-qm', 'baseline'], check=True)
        (repo / 'code.txt').write_text('changed')
        return {'repository': temp, 'patch_sha256': digest(patch(repo)),
                'source_hashes': json.loads(json.dumps(snapshot(repo))),
                'findings': [{'id': 'R1'}], 'checks': [{'exit_code': 0}]}

    def test_parent_cannot_waive_failed_checks_or_accept_product(self):
        from tempfile import TemporaryDirectory
        from dispute_review import resolve_parent
        decision = {'author': 'hosted_parent', 'resolutions': [
            {'id': 'R1', 'decision': 'withdrawn', 'reason': 'counterexample verified'}]}
        with TemporaryDirectory() as temp:
            packet = self.fixture(temp)
            result = resolve_parent(packet, decision)
            self.assertEqual(result['status'], 'findings_resolved')
            self.assertFalse(result['product_accepted'])
            packet['checks'][0]['exit_code'] = 1
            self.assertEqual(resolve_parent(packet, decision)['status'], 'blocked_checks')

    def test_parent_requires_current_source_and_explicit_complete_decision(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from dispute_review import resolve_parent
        with TemporaryDirectory() as temp:
            packet = self.fixture(temp)
            for decision in ({'author': 'hosted_parent', 'resolutions': []}, {'resolutions': []}):
                with self.assertRaises(ValueError):
                    resolve_parent(packet, decision)
            (Path(temp) / 'code.txt').write_text('changed again')
            with self.assertRaises(ValueError):
                resolve_parent(packet, {'author': 'hosted_parent', 'resolutions': []})


class EscalationPolicyTests(unittest.TestCase):
    def test_failed_checks_cannot_be_outvoted_by_withdrawn_findings(self):
        from dispute_review import needs_escalation
        withdrawn = {'R1': {'decision': 'withdrawn'}}
        self.assertFalse(needs_escalation(withdrawn, True))
        self.assertTrue(needs_escalation(withdrawn, False))
        self.assertTrue(needs_escalation({'R1': {'decision': 'upheld'}}, True))
        self.assertTrue(needs_escalation({'R1': {'decision': 'uncertain'}}, True))


class OutputFallbackTests(unittest.TestCase):
    def test_bad_opinion_output_emits_parent_packet(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from unittest.mock import patch
        import json
        import dispute_review
        with TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / 'repo'
            repo.mkdir()
            ParentDecisionTests().fixture(str(repo))
            (root / 'config.json').write_text(json.dumps({'repository': str(repo)}))
            (root / 'task.json').write_text(json.dumps({'id': 'T', 'title': 'fixture',
                                                     'allowed_files': ['code.txt']}))
            (root / 'findings.json').write_text(json.dumps([{'id': 'R1'}]))
            def agent(config, task, directory):
                return SimpleNamespace(repo=repo, latest_checks=[],
                                       checks=lambda prefix: (True, [{'exit_code': 0, 'log': 'check.log'}]))
            case = {'name': 'fixture', 'config': 'config.json', 'task': 'task.json',
                    'findings_file': 'findings.json'}
            with patch.object(dispute_review, 'ROOT', root), patch.object(dispute_review, 'Runner', side_effect=agent),                  patch.object(dispute_review, 'opinion', side_effect=ValueError('bad JSON')):
                result = dispute_review.run_case(case)
            self.assertEqual(result['status'], 'parent_required')
            self.assertFalse(result['product_accepted'])
            self.assertTrue((root / result['run'] / 'parent-packet.json').exists())
