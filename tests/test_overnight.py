import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import overnight
import runner
import test_runner


class OvernightTests(unittest.TestCase):
    def manifest(self):
        now=datetime.now(timezone.utc)
        config={'repository':'/tmp/example','checks':[{'name':'unit','cwd':'.','argv':['true']}],
                'max_rounds':3,'min_review_rounds':1,'check_timeout_seconds':20,
                'invocation_timeout_seconds':30,'local_only':True}
        task={'id':'T','title':'Task','problem':'Outcome','allowed_files':['code.py'],
              'acceptance_criteria':['Correct']}
        entry={'id':'a1','repository':'a','not_before':(now-timedelta(seconds=2)).isoformat(),
               'base':'0123456789abcdef','config':config,'task':task}
        return {'start':(now-timedelta(seconds=3)).isoformat(),
                'deadline':(now+timedelta(seconds=120)).isoformat(),'max_task_seconds':60,
                'entries':[entry]}

    def test_schedule_favors_unserved_repositories_without_early_release(self):
        manifest=self.manifest(); a=manifest['entries'][0]
        b=dict(a,id='b1',repository='b')
        a2=dict(a,id='a2')
        future=dict(a,id='c1',repository='c',not_before=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        results=[{'entry_id':'a1','repository':'a'}]
        self.assertEqual(overnight.next_task([a,a2,b,future],results,time.time())['id'],'b1')
        self.assertIsNone(overnight.next_task([future],[],time.time()))

    def test_manifest_rejects_hosted_entries_unfrozen_base_and_unzoned_times(self):
        for change in ('hosted','base','time','duplicate'):
            m=self.manifest()
            if change=='hosted':m['entries'][0]['config']['local_only']=False
            if change=='base':m['entries'][0]['base']='HEAD'
            if change=='time':m['start']='2026-11-01T22:00:00'
            if change=='duplicate':m['entries']*=2
            with self.subTest(change=change),self.assertRaises(ValueError):overnight.check_manifest(m)

    def test_escalation_is_parked_and_next_task_runs_without_hosted_continuation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);m=self.manifest()
            m['entries'].append(dict(m['entries'][0],id='b1',repository='b',task=dict(m['entries'][0]['task'],id='T2')))
            path=root/'manifest.json';path.write_text(json.dumps(m))
            jobs=[root/'job1',root/'job2']; seen=[]
            def create(config,*args):
                self.assertLessEqual(config['deadline_epoch'],time.time()+61)
                seen.append(args);return jobs[len(seen)-1]
            def describe(job):return {'status':'parent_required' if job==jobs[0] else 'accepted'}
            with patch.object(overnight,'create_job',side_effect=create),patch.object(overnight,'setup'),\
                 patch.object(overnight,'invoke_job',side_effect=[2,0]),patch.object(overnight,'describe',side_effect=describe):
                self.assertEqual(overnight.execute(path),0)
            summary=json.loads((root/'summary.json').read_text())
            self.assertEqual([r['status'] for r in summary['results']],['parent_required','accepted'])
            self.assertFalse(summary['hosted_escalation_enabled'])
            with self.assertRaisesRegex(RuntimeError,'already started'):overnight.execute(path)

    def test_deadline_marks_unattempted_work_without_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); m=self.manifest()
            old=datetime.now(timezone.utc)-timedelta(hours=1)
            m.update(start=(old-timedelta(seconds=70)).isoformat(),deadline=old.isoformat())
            m['entries'][0]['not_before']=m['start']
            path=root/'manifest.json';path.write_text(json.dumps(m))
            with patch.object(overnight,'create_job') as create:
                self.assertEqual(overnight.execute(path),0);create.assert_not_called()
            self.assertEqual(json.loads((root/'summary.json').read_text())['results'][0]['status'],'not_run_deadline')


class LocalOnlyTests(unittest.TestCase):
    def fixture(self,temp):
        return test_runner.RunnerTests().make_trial_runner(temp,2,1)

    def test_local_endpoint_is_required_and_public_provider_rejected(self):
        for endpoint in ('','https://api.anthropic.com','http://8.8.8.8','http://user:pass@127.0.0.1'):
            with tempfile.TemporaryDirectory() as temp:
                obj=self.fixture(temp)
                with patch.dict(os.environ,{'ANTHROPIC_BASE_URL':endpoint,'ANTHROPIC_MODEL':'local-qwen'}):
                    with self.assertRaisesRegex(ValueError,'Local-only'):
                        runner.Runner(dict(obj.config,local_only=True),obj.task,obj.directory)

    def test_local_only_invocation_uses_bare_explicit_model_and_deadline(self):
        with tempfile.TemporaryDirectory() as temp,contextlib.redirect_stdout(io.StringIO()):
            obj=self.fixture(temp)
            config=dict(obj.config,local_only=True,claude='fake',invocation_timeout_seconds=3600,deadline_epoch=time.time()+15)
            with patch.dict(os.environ,{'ANTHROPIC_BASE_URL':'http://192.168.1.248:8080',
                                        'ANTHROPIC_MODEL':'local-qwen','ANTHROPIC_AUTH_TOKEN':'local-test',
                                        'CLAUDE_CODE_USE_BEDROCK':'1','HTTPS_PROXY':'http://proxy'}):
                obj=runner.Runner(config,obj.task,obj.directory)
            captured=[]
            def process(argv,cwd,output,timeout,env,prompt=None):
                captured.append((argv,timeout,env,prompt))
                output.write_text(json.dumps({'type':'result','result':'report'}));return 0
            with patch.object(runner,'run_process',side_effect=process):obj.invoke('reviewer',1,'Review')
            argv,timeout,env,prompt=captured[0]
            self.assertIn('--bare',argv);self.assertIn('--disable-slash-commands',argv)
            self.assertEqual(argv[argv.index('--setting-sources')+1],'')
            self.assertEqual(argv[argv.index('--model')+1],'local-qwen')
            self.assertNotIn('--fallback-model',argv)
            self.assertLessEqual(timeout,15)
            self.assertNotIn('CLAUDE_CODE_USE_BEDROCK',env);self.assertNotIn('HTTPS_PROXY',env)
            self.assertEqual(env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'],'1')
            self.assertIn('offline local-only batch',prompt)
            obj.config['deadline_epoch']=time.time()-1
            with self.assertRaises(TimeoutError):obj.time_limit(30)


if __name__=='__main__':unittest.main()
