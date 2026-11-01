#!/usr/bin/env python3
"""Local coding delegation for Codex. Standard library only; Linux/WSL."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from runner import ROOT, Runner, git


def home():
    return Path(os.environ.get('AI_ORCHESTRATOR_HOME', '~/.local/share/ai-orchestrator')).expanduser().resolve()


def read(path):
    return json.loads(Path(path).expanduser().read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
        raise ValueError('Names require 1–80 letters, digits, dots, underscores or hyphens')
    return value


def profile_path(name):
    return home() / 'profiles' / (safe_name(name) + '.json')


def load_profile(name):
    path = profile_path(name)
    config = read(path)
    repo = Path(config['repository']).expanduser().resolve()
    if Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip()).resolve() != repo:
        raise ValueError('Profile repository must be the Git root')
    config['repository'] = str(repo)
    for key in ('guide', 'test_guide'):
        if config.get(key):
            target = Path(config[key]).expanduser()
            config[key] = str((path.parent / target).resolve()) if not target.is_absolute() else str(target)
    validate(config)
    return config


def validate(config, task=None):
    if not config.get('checks'):
        raise ValueError('Configure at least one mandatory repository check')
    for key in ('max_rounds', 'min_review_rounds', 'invocation_timeout_seconds', 'check_timeout_seconds'):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError(key + ' must be a positive integer')
    if type(config.get('review_output_attempts', 2)) is not int or config.get('review_output_attempts', 2) < 1:
        raise ValueError('review_output_attempts must be a positive integer')
    if not 1 <= config['min_review_rounds'] <= config['max_rounds']:
        raise ValueError('Require 1 <= min_review_rounds <= max_rounds')
    names = set()
    for check in config['checks'] + config.get('acceptance_checks', []) + config.get('setup', []):
        safe_name(check['name'])
        if check['name'] in names:
            raise ValueError('Check/setup names must be unique')
        names.add(check['name'])
        if not check.get('argv') or not all(isinstance(v, str) for v in check['argv']):
            raise ValueError('Commands must be nonempty argv arrays of strings')
        cwd = Path(check.get('cwd', '.'))
        if cwd.is_absolute() or '..' in cwd.parts:
            raise ValueError('Command cwd must stay inside the worktree')
        check.setdefault('cwd', '.')
    if task is not None:
        safe_name(task['id'])
        for key in ('title', 'problem'):
            if not isinstance(task.get(key), str) or not task[key].strip():
                raise ValueError('Task requires a nonempty ' + key)
        for key in ('allowed_files', 'acceptance_criteria'):
            if not isinstance(task.get(key), list) or not task[key] or not all(isinstance(v, str) and v.strip() for v in task[key]):
                raise ValueError('Task requires nonempty ' + key)
        for name in task['allowed_files']:
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or name in ('.', '') or '.git' in path.parts:
                raise ValueError('Allowed files must be explicit repository-relative paths')
        if len(set(task['allowed_files'])) != len(task['allowed_files']):
            raise ValueError('Allowed files must be unique')
        if not set(task.get('required_changed_files', [])) <= set(task['allowed_files']):
            raise ValueError('Required files must be allowed files')


def initialize(args):
    path = profile_path(args.name)
    if path.exists():
        raise ValueError('Profile exists; edit it explicitly: ' + str(path))
    repo = Path(args.repo).expanduser().resolve()
    git(repo, 'rev-parse', '--verify', 'HEAD')
    path.parent.mkdir(parents=True, exist_ok=True)
    guide = path.with_suffix('.md')
    if guide.exists():
        raise ValueError('Guide already exists: ' + str(guide))
    checks = [json.loads(check) for check in args.check]
    config = {'repository': str(repo), 'guide': guide.name, 'claude': 'claude',
              'max_rounds': 4, 'min_review_rounds': 1, 'dispute_escalation': True,
              'review_output_attempts': 2, 'invocation_timeout_seconds': 3600,
              'check_timeout_seconds': 600, 'checks': checks, 'setup': []}
    if checks:
        validate(config)
    write(path, config)
    guide.write_text('# Repository guide\n\nAdd a short architecture summary, test conventions, dependency setup,\n'
                     'and any operational constraints. Commands and setup belong in the profile.\n')
    print(json.dumps({'profile': str(path), 'guide': str(guide),
                      'next': 'Edit the profile/guide, then run doctor. Checks are required before execution.'}))
    return 0


def create_job(config, task, profile, base='HEAD'):
    validate(config, task)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    job = home() / 'runs' / (stamp + '-' + task['id'])
    job.mkdir(parents=True)
    source = Path(config['repository'])
    revision = os.fsdecode(git(source, 'rev-parse', '--verify', base + '^{commit}')).strip()
    worktree = job / 'worktree'
    # No branch, no reset, no dependency copying, no changes to the source checkout.
    subprocess.run(['git', '-C', str(source), 'worktree', 'add', '--detach', str(worktree), revision],
                   check=True, stdout=subprocess.DEVNULL)
    config = dict(config, repository=str(worktree))
    # Detect escaped symlinks against the actual isolated checkout, not the source tree.
    if any(not (worktree / name).resolve().is_relative_to(worktree) for name in task['allowed_files']):
        raise ValueError('Allowed file resolves outside worktree; retained at ' + str(job))
    write(job / 'config.json', config)
    write(job / 'task.json', task)
    write(job / 'job.json', {'profile': profile, 'source_repository': str(source),
                             'base_commit': revision, 'worktree': str(worktree), 'task': task['id']})
    return job


def setup(job):
    config = read(job / 'config.json')
    # Use the same literal environment loader as model/check execution.
    agent = Runner(config, read(job / 'task.json'), job)
    from runner import run_process
    for command in config.get('setup', []):
        code = run_process(command['argv'], agent.repo / command['cwd'],
                           job / ('setup-' + command['name'] + '.log'),
                           config['check_timeout_seconds'], agent.env)
        if code:
            raise RuntimeError('Dependency setup failed: ' + command['name'])
    if git(agent.repo, 'status', '--porcelain').strip():
        raise RuntimeError('Setup left unignored files; configure repository ignores before running')


def invoke_job(job, decision=None):
    artifacts = job / 'artifacts'
    argv = [sys.executable, str(ROOT / 'runner.py'), '--config', str(job / 'config.json'),
            '--task', str(job / 'task.json'), '--run-dir', str(artifacts)]
    if decision:
        argv += ['--resume', '--decision', str(Path(decision).expanduser().resolve())]
    with (job / 'runner.log').open('a') as log:
        process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait()
        except KeyboardInterrupt:
            process.send_signal(__import__('signal').SIGINT)
            process.wait()
            raise
    return code


def describe(job):
    artifacts = job / 'artifacts'
    state_path = artifacts / 'state.json'
    state = read(state_path) if state_path.exists() else {'status': 'not_started'}
    if (job / 'failure.json').exists() and not state_path.exists():
        state = read(job / 'failure.json')
    metadata = read(job / 'job.json')
    result = {'run': str(job), **metadata, **state, 'log': str(job / 'runner.log')}
    if (artifacts / 'accepted.patch').exists():
        result['patch'] = str(artifacts / 'accepted.patch')
    if (artifacts / 'parent-packet.json').exists():
        result['parent_packet'] = str(artifacts / 'parent-packet.json')
    return result


def resolve_job(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = home() / 'runs' / value
    path = path.resolve()
    if not (path / 'job.json').is_file():
        raise ValueError('Not an orchestrator run: ' + str(path))
    return path


def run(args):
    config = load_profile(args.profile)
    task = read(args.task)
    if args.acceptance:
        config['acceptance_checks'] = config.get('acceptance_checks', []) + read(args.acceptance)
    job = create_job(config, task, args.profile, args.base)
    print('Run: ' + str(job), flush=True)
    try:
        setup(job)
        code = invoke_job(job)
    except Exception as error:
        write(job / 'failure.json', {'status': 'setup_or_launch_failed', 'reason': str(error)})
        raise
    print(json.dumps(describe(job), indent=2))
    return code


def queue(args):
    config = load_profile(args.profile)
    revision = os.fsdecode(git(Path(config['repository']), 'rev-parse', '--verify', args.base + '^{commit}')).strip()
    tasks = [read(path) for path in args.task]
    for task in tasks:
        validate(config, task)
    queue_dir = home() / 'queues' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    queue_dir.mkdir(parents=True)
    write(queue_dir / 'contract.json', {'config': config, 'tasks': tasks, 'base': revision})
    results = []
    for task in tasks:
        job = None
        try:
            job = create_job(config, task, args.profile, revision)
            setup(job)
            code = invoke_job(job)
            result = {**describe(job), 'exit_code': code}
        except Exception as error:
            result = {'task': task['id'], 'status': 'setup_or_launch_failed', 'reason': str(error)}
            if job:
                write(job / 'failure.json', result)
                result['run'] = str(job)
        results.append(result)
        write(queue_dir / 'summary.json', results)
    print(json.dumps({'queue': str(queue_dir), 'results': results}, indent=2))
    return 0 if all(r.get('status') == 'accepted' for r in results) else 1


def doctor(args):
    config = load_profile(args.profile)
    if not shutil.which(config['claude']):
        raise ValueError('Claude executable not found: ' + config['claude'])
    task = {'id': 'doctor', 'title': 'Verify repository onboarding', 'problem': 'Baseline checks only',
            'allowed_files': ['__onboarding_probe__'], 'acceptance_criteria': ['Baseline passes']}
    job = create_job(config, task, args.profile)
    setup(job)
    artifacts = job / 'artifacts'
    artifacts.mkdir()
    agent = Runner(read(job / 'config.json'), task, artifacts)
    agent.state('baseline')
    passed, checks = agent.checks('baseline')
    agent.guard()
    agent.state('ready' if passed else 'baseline_failed', checks=checks)
    print(json.dumps(describe(job), indent=2))
    return 0 if passed else 1


def resume(args):
    job = resolve_job(args.run)
    with (job / 'resume.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code = invoke_job(job, args.decision)
    print(json.dumps(describe(job), indent=2))
    return code


def install(args):
    codex_home = Path(args.codex_home or os.environ.get('CODEX_HOME', '~/.codex')).expanduser().resolve()
    target = codex_home / 'skills' / 'local-coding-loop'
    source = ROOT / 'skills' / 'local-coding-loop'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == source:
        pass
    elif target.exists() or target.is_symlink():
        raise ValueError('Skill path exists; will not overwrite: ' + str(target))
    else:
        target.symlink_to(source, target_is_directory=True)
    bindir = Path(args.bin_dir).expanduser().resolve()
    bindir.mkdir(parents=True, exist_ok=True)
    launcher = bindir / 'ai-orchestrator'
    content = '#!/bin/sh\nexec ' + __import__('shlex').quote(sys.executable) + ' ' + __import__('shlex').quote(str(ROOT / 'orchestrator.py')) + ' "$@"\n'
    if launcher.exists() and launcher.read_text() != content:
        raise ValueError('Launcher exists; will not overwrite: ' + str(launcher))
    launcher.write_text(content)
    launcher.chmod(0o755)
    print(json.dumps({'skill': str(target), 'command': str(launcher),
                      'note': 'Keep this checkout in place. Open a new Codex session to discover the skill.'}))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init', help='Create a reusable repository profile and guide')
    p.add_argument('name'); p.add_argument('--repo', default='.')
    p.add_argument('--check', action='append', default=[], help='JSON check object with name/cwd/argv; repeatable')
    p.set_defaults(func=initialize)
    p = sub.add_parser('doctor', help='Verify dependencies and baseline in a fresh isolated worktree; no model calls')
    p.add_argument('profile'); p.set_defaults(func=doctor)
    p = sub.add_parser('run', help='Run one task unattended in an isolated worktree')
    p.add_argument('profile'); p.add_argument('--task', required=True); p.add_argument('--base', default='HEAD')
    p.add_argument('--acceptance', help='JSON array of additional task checks')
    p.set_defaults(func=run)
    p = sub.add_parser('queue', help='Run independent tasks sequentially from one frozen base, continuing past failures')
    p.add_argument('profile'); p.add_argument('--task', action='append', required=True)
    p.add_argument('--base', default='HEAD'); p.set_defaults(func=queue)
    p = sub.add_parser('status', help='Read one saved summary; does not invoke models')
    p.add_argument('run'); p.set_defaults(func=lambda args: print(json.dumps(describe(resolve_job(args.run)), indent=2)) or 0)
    p = sub.add_parser('resume', help='Continue a parent_required run with a hosted parent decision')
    p.add_argument('run'); p.add_argument('--decision', required=True); p.set_defaults(func=resume)
    p = sub.add_parser('install', help='Link the Codex skill and install a small CLI launcher')
    p.add_argument('--codex-home'); p.add_argument('--bin-dir', default='~/.local/bin'); p.set_defaults(func=install)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; artifacts and worktree retained.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
