#!/usr/bin/env python3
"""Read-only dispute replay: original reconsideration, fresh opinion, parent packet.

This experiment never changes product code or promotes a patch to accepted.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from runner import ROOT, Runner, digest, patch, parse_review, snapshot, validate_review_evidence


def resolutions(review, findings):
    expected = {finding['id'] for finding in findings}
    rows = review.get('resolutions')
    if not isinstance(rows, list):
        raise ValueError('resolutions must list every disputed finding')
    decisions = {}
    active = {finding['id'] for finding in review['findings']}
    if not active <= expected:
        raise ValueError('Do not introduce unrelated findings in dispute adjudication')
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('resolution must be an object')
        identity, decision = row.get('id'), row.get('decision')
        if not isinstance(identity, str) or identity not in expected or identity in decisions:
            raise ValueError('Each disputed ID needs exactly one resolution')
        if decision not in ('withdrawn', 'upheld', 'uncertain') or not isinstance(row.get('reason'), str) or not row['reason'].strip():
            raise ValueError('Resolution needs a decision and evidence-based reason')
        if (decision == 'withdrawn') == (identity in active):
            raise ValueError('Resolution contradicts active findings')
        decisions[identity] = row
    if set(decisions) != expected:
        raise ValueError('Missing disputed finding resolutions')
    return decisions


def opinion(agent, persona, findings, before):
    error = ''
    for attempt in range(1, agent.config.get('review_output_attempts', 3) + 1):
        agent.review_attempt = attempt
        report = agent.invoke(persona, 1, '''Reconsider ONLY these open findings. No code changes.
Also return "resolutions": [{"id":"R1","decision":"withdrawn|upheld|uncertain",
"reason":"Address the implementer's evidence explicitly"}].
Return one resolution per supplied ID. Withdrawn IDs must be absent from findings;
upheld or uncertain IDs remain in findings. Include standard verdict, summary,
all acceptance-criterion coverage, and source-ID evidence.''' + error)
        if snapshot(agent.repo) != before:
            raise RuntimeError('Read-only opinion mutated source')
        try:
            review = validate_review_evidence(parse_review(report), agent.repo, agent.task)
            resolved = resolutions(review, findings)
            agent.append(persona + ' opinion', json.dumps(review, indent=2))
            (agent.directory / (persona + '-resolved.json')).write_text(json.dumps(review, indent=2))
            return review, resolved
        except ValueError as failure:
            agent.append(persona + ' invalid output', str(failure))
            error = '\nOUTPUT VALIDATION ERROR: ' + str(failure) + '\nCorrect the complete JSON, retaining all criterion coverage.'
    raise ValueError('Dispute opinion output retries exhausted: ' + error)


def needs_escalation(decisions, checks_passed):
    return not checks_passed or any(row['decision'] != 'withdrawn' for row in decisions.values())


def run_case(case):
    config = json.loads((ROOT / case['config']).read_text())
    task = json.loads((ROOT / case['task']).read_text())
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory = ROOT / 'runs' / ('dispute-' + stamp + '-' + case['name'])
    directory.mkdir(parents=True)
    (directory / 'config.json').write_text(json.dumps(config, indent=2))
    (directory / 'task.json').write_text(json.dumps(task, indent=2))
    agent = Runner(config, task, directory)
    # Case expectations never enter task, guide, handoff, or model prompt.
    findings = json.loads((ROOT / case['findings_file']).read_text())
    if isinstance(findings, dict):
        findings = findings['findings']
    response = (ROOT / case['response_file']).read_text() if case.get('response_file') else ''
    agent.latest_review = {'findings': findings}
    agent.latest_implementation = response
    before = snapshot(agent.repo)
    frozen_patch = patch(agent.repo)
    result = {'case': case['name'], 'run': str(directory.relative_to(ROOT)),
              'patch_sha256': digest(frozen_patch), 'product_accepted': False}
    try:
        passed, checks = agent.checks('dispute-input')
        result['checks_passed'] = passed
        for check in agent.latest_checks:
            if check['exit_code']:
                check['failure_output'] = (directory / check['log']).read_text(errors='replace')[-2000:]
        first, decisions = opinion(agent, 'reviewer', findings, before)
        result['original_decisions'] = decisions
        if not needs_escalation(decisions, passed):
            result['status'] = 'withdrawn'
        else:
            # A fresh perspective gets the dispute and rebuttal, not the earlier verdict.
            _, second = opinion(agent, 'adjudicator', findings, before)
            result['second_decisions'] = second
            # Still-disputed claims go to the hosted parent, never a retry/vote override.
            result['status'] = 'parent_required'
            packet = {'task': task, 'repository': str(agent.repo),
                      'patch_sha256': digest(frozen_patch), 'findings': findings,
                      'implementer_response': response[:6000], 'original_review': first,
                      'second_opinion': second, 'checks': checks,
                      'source_hashes': {name: before.get(name) for name in task['allowed_files']},
                      'decision_required': 'Adjudicate each finding from evidence; mandatory checks cannot be waived.'}
            (directory / 'parent-packet.json').write_text(json.dumps(packet, indent=2))
    except ValueError as error:
        result.update(status='parent_required', reason=str(error))
        packet = {'task': task, 'repository': str(agent.repo),
                  'patch_sha256': digest(frozen_patch), 'findings': findings,
                  'implementer_response': response[:6000],
                  'original_review': locals().get('first'),
                  'second_opinion': {'status': 'invalid_output', 'reason': str(error)},
                  'checks': locals().get('checks', []),
                  'source_hashes': {name: before.get(name) for name in task['allowed_files']},
                  'decision_required': 'Adjudicate each finding; mandatory checks cannot be waived.'}
        (directory / 'parent-packet.json').write_text(json.dumps(packet, indent=2))
    except Exception as error:
        result.update(status='stopped', reason=str(error))
    if snapshot(agent.repo) != before or patch(agent.repo) != frozen_patch:
        raise RuntimeError('Dispute replay changed the product')
    (directory / 'result.json').write_text(json.dumps(result, indent=2))
    return result


def resolve_parent(packet, decision):
    """Record explicit parent findings without promoting a product patch."""
    repo = Path(packet['repository'])
    if digest(patch(repo)) != packet['patch_sha256']:
        raise ValueError('Parent decision is stale: patch changed')
    current = json.loads(json.dumps(snapshot(repo)))
    if any(current.get(name) != value for name, value in packet['source_hashes'].items()):
        raise ValueError('Parent decision is stale: source changed')
    if decision.get('author') != 'hosted_parent':
        raise ValueError('Decision must identify the hosted parent')
    rows = decision.get('resolutions', [])
    active = [{'id': row.get('id')} for row in rows
              if isinstance(row, dict) and row.get('decision') != 'withdrawn']
    resolved = resolutions({'findings': active, 'resolutions': rows}, packet['findings'])
    checks_passed = bool(packet['checks']) and all(check['exit_code'] == 0 for check in packet['checks'])
    choices = {row['decision'] for row in resolved.values()}
    status = 'unresolved' if 'uncertain' in choices else ('changes_required' if 'upheld' in choices else 'findings_resolved')
    if not checks_passed:
        status = 'blocked_checks'
    return {'author': 'hosted_parent', 'status': status, 'resolutions': resolved,
            'patch_sha256': packet['patch_sha256'], 'checks_passed': checks_passed,
            'product_accepted': False,
            'recorded_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--manifest')
    source.add_argument('--parent-packet')
    parser.add_argument('--decision')
    args = parser.parse_args()
    if args.parent_packet:
        if not args.decision:
            parser.error('--decision is required with --parent-packet')
        packet_path = ROOT / args.parent_packet
        result = resolve_parent(json.loads(packet_path.read_text()), json.loads((ROOT / args.decision).read_text()))
        (packet_path.parent / 'parent-decision.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
        return
    cases = json.loads((ROOT / args.manifest).read_text())
    results = [run_case(case) for case in cases]
    output = ROOT / 'runs/dispute-suite-results.json'
    output.write_text(json.dumps(results, indent=2))
    print(str(output))


if __name__ == '__main__':
    main()
