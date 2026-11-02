#!/usr/bin/env python3
"""One-shot local-only multi-repository overnight batch; no hosted client or wakeup."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sys
import time

from orchestrator import create_job, describe, invoke_job, setup, validate, write


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Schedule timestamps require a timezone offset')
    return parsed.timestamp()


def next_task(entries, results, now):
    finished = {r['entry_id'] for r in results}
    counts = {}
    for result in results:
        counts[result['repository']] = counts.get(result['repository'], 0) + 1
    eligible = [e for e in entries if e['id'] not in finished and timestamp(e['not_before']) <= now]
    return min(eligible, key=lambda e: (counts.get(e['repository'], 0), timestamp(e['not_before']), e['id'])) if eligible else None


def report(directory, manifest, results, status):
    data = {'status': status, 'local_only': True, 'hosted_escalation_enabled': False,
            'start': manifest['start'], 'deadline': manifest['deadline'],
            'updated_at': datetime.now(timezone.utc).isoformat(), 'results': results}
    # This supervisor has no hosted invocation path.
    # Implementation tools are trusted local execution, not a network sandbox.
    temporary = directory / 'summary.tmp'
    write(temporary, data)
    temporary.replace(directory / 'summary.json')
    lines = ['# Overnight coding batch', '', f'Status: {status}', '',
             'Local-only inference. Candidate patches remain isolated and uncommitted.', '',
             '| Repository | Task | Outcome | Artifacts |', '|---|---|---|---|']
    for result in results:
        lines.append(f"| {result['repository']} | {result['task']} | {result['status']} | {result.get('run', result.get('reason', ''))} |")
    (directory / 'MORNING-REPORT.md').write_text('\n'.join(lines) + '\n')


def check_manifest(manifest):
    start, deadline = timestamp(manifest['start']), timestamp(manifest['deadline'])
    if deadline <= start or not 60 <= manifest['max_task_seconds'] <= deadline - start:
        raise ValueError('Invalid overnight/task time bounds')
    ids = set()
    for entry in manifest['entries']:
        if entry['id'] in ids:
            raise ValueError('Duplicate entry ID')
        ids.add(entry['id'])
        if not start <= timestamp(entry['not_before']) < deadline:
            raise ValueError('Repository release time outside overnight window')
        if not entry['config'].get('local_only'):
            raise ValueError('Every overnight entry must require local-only inference')
        validate(entry['config'], entry['task'])
        if not entry.get('base') or entry['base'] == 'HEAD':
            raise ValueError('Freeze each repository to an explicit commit')
    return start, deadline


def execute(path):
    manifest = json.loads(path.read_text())
    start, deadline = check_manifest(manifest)
    directory = path.parent
    results = []
    if (directory / 'summary.json').exists():
        # Never automatically repeat a partially completed batch after a restart.
        raise RuntimeError('This batch already started; preserved summary exists')
    report(directory, manifest, results, 'waiting')
    while time.time() < start:
        time.sleep(min(60, start - time.time()))
    while len(results) < len(manifest['entries']):
        now = time.time()
        if now >= deadline:
            for entry in manifest['entries']:
                if entry['id'] not in {r['entry_id'] for r in results}:
                    results.append({'entry_id': entry['id'], 'repository': entry['repository'],
                                    'task': entry['task']['id'], 'status': 'not_run_deadline'})
            break
        entry = next_task(manifest['entries'], results, now)
        if entry is None:
            pending = [timestamp(e['not_before']) for e in manifest['entries']
                       if e['id'] not in {r['entry_id'] for r in results}]
            time.sleep(max(0.01, min(60, min(pending) - now, deadline - now)))
            continue
        record = {'entry_id': entry['id'], 'repository': entry['repository'], 'task': entry['task']['id'],
                  'started_at': datetime.now(timezone.utc).isoformat()}
        job = None
        try:
            config = dict(entry['config'], deadline_epoch=min(deadline, now + manifest['max_task_seconds']))
            job = create_job(config, entry['task'], entry['repository'], entry['base'])
            record['run'] = str(job)
            report(directory, manifest, results + [{**record, 'status': 'running'}], 'running')
            setup(job)
            code = invoke_job(job)
            summary = describe(job)
            record.update(status=summary['status'], exit_code=code,
                          **{k: summary[k] for k in ('patch', 'parent_packet', 'reason') if k in summary})
            # parent_required is parked; there is deliberately no automatic hosted continuation.
        except Exception as error:
            record.update(status='setup_or_launch_failed', reason=str(error))
            if job:
                write(job / 'failure.json', record)
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        results.append(record)
        report(directory, manifest, results, 'running')
    report(directory, manifest, results, 'complete')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    path = Path(args.manifest).resolve()
    manifest = json.loads(path.read_text())
    check_manifest(manifest)
    if args.validate:
        print(json.dumps({'entries': len(manifest['entries']), 'local_only': True,
                          'repositories': sorted({e['repository'] for e in manifest['entries']})}))
        return 0
    lock_path = Path(os.environ.get('AI_ORCHESTRATOR_HOME', '~/.local/share/ai-orchestrator')).expanduser() / 'overnight.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return execute(path)


if __name__ == '__main__':
    sys.exit(main())
