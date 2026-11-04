#!/usr/bin/env python3
"""Bounded task runner. No model owns acceptance or runner state."""
import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import ipaddress
from urllib.parse import urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
import os
import re
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def snapshot(repo):
    paths = git(repo, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
    result = {}
    for raw in paths:
        if raw:
            name = os.fsdecode(raw)
            path = repo / name
            if path.is_symlink():
                result[name] = ('link', os.readlink(path))
            elif path.is_file():
                result[name] = (path.stat().st_mode & 0o777, digest(path.read_bytes()))
            else:
                result[name] = None
    return result


def changed(before, after):
    return {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}


def patch(repo):
    data = git(repo, 'diff', '--binary', 'HEAD', '--')
    for raw in git(repo, 'ls-files', '-z', '--others', '--exclude-standard').split(b'\0'):
        if raw:
            result = subprocess.run(['git', 'diff', '--no-index', '--binary', '--', '/dev/null', os.fsdecode(raw)],
                                    cwd=repo, capture_output=True)
            if result.returncode not in (0, 1):
                raise RuntimeError('Could not capture untracked diff')
            data += result.stdout
    return data


class InferenceUnavailable(RuntimeError):
    pass


class NoHealthRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def probe_inference(env, timeout=5, *, active=False):
    endpoint = urlsplit(env['ANTHROPIC_BASE_URL'])
    url = urlunsplit((endpoint.scheme, endpoint.netloc, '/health', '', ''))
    opener = build_opener(ProxyHandler({}), NoHealthRedirect())
    try:
        with opener.open(url, timeout=timeout) as response:
            if response.status != 200:
                raise InferenceUnavailable(f'Inference health returned HTTP {response.status}')
    except HTTPError as error:
        error.close()
        # A saturated llama.cpp server can return 503 while serving an active request.
        if not (active and error.code == 503):
            raise InferenceUnavailable(f'Inference health returned HTTP {error.code}') from error
    except (URLError, OSError) as error:
        raise InferenceUnavailable('Local inference health connection failed') from error


def check_inference(config):
    if config.get('local_only'):
        env = model_environment(config)
        def probe():
            remaining = config.get('deadline_epoch', float('inf')) - time.time()
            if remaining <= 0:
                raise TimeoutError('Task/overnight deadline reached')
            probe_inference(env, min(5, remaining))

        try:
            probe()
        except InferenceUnavailable:
            probe()


def run_process(argv, cwd, output, timeout, env, prompt=None, heartbeat=None):
    """Preserve output; kill entire process group on timeout or interruption."""
    with output.open('wb') as log:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE if prompt else subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + timeout
            input_data = prompt.encode() if prompt else None
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, timeout)
                try:
                    proc.communicate(input=input_data, timeout=min(30, remaining) if heartbeat else remaining)
                    break
                except subprocess.TimeoutExpired:
                    if heartbeat is None or remaining <= 30:
                        raise
                    input_data = None
                    heartbeat(deadline - time.monotonic())
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            raise
    return proc.returncode


def parse_envelope(text):
    # Claude may write diagnostic warnings before the single JSON result.
    for line in reversed(text.splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get('type') == 'result':
            return value
    raise ValueError('Claude returned no JSON result envelope')


def parse_review(text):
    value = text.strip()
    if value.startswith('```'):
        value = '\n'.join(value.splitlines()[1:-1])
    review = json.loads(value)
    if not isinstance(review, dict) or review.get('verdict') not in ('approve', 'request_changes'):
        raise ValueError('Invalid review verdict')
    if not isinstance(review.get('summary'), str) or not isinstance(review.get('findings'), list):
        raise ValueError('Review requires summary and findings')
    ids = set()
    for finding in review['findings']:
        if not isinstance(finding, dict) or any(not isinstance(finding.get(k), str) or not finding[k].strip()
                                               for k in ('id', 'file', 'issue', 'requested_change')):
            raise ValueError('Malformed review finding')
        if finding['id'] in ids:
            raise ValueError('Duplicate finding ID')
        ids.add(finding['id'])
    if (review['verdict'] == 'approve') != (not review['findings']):
        raise ValueError('Verdict contradicts findings')
    return review


def validate_review_evidence(review, repo, task):
    """Resolve unique exact quotes; preserve supplied lines as audit metadata.

    Validate source anchors and criterion coverage, not the reviewer's reasoning.
    Collect all errors so a single retry can address the entire output.
    """
    resolved = copy.deepcopy(review)
    errors = []

    def citations(items, location):
        if not isinstance(items, list) or not items:
            errors.append(location + ': source evidence is required')
            return
        for index, item in enumerate(items):
            label = f'{location}[{index}]'
            if not isinstance(item, dict):
                errors.append(label + ': evidence must be an object')
                continue
            if 'anchor' in item:
                anchor = item['anchor']
                match = re.fullmatch(r'S([1-9][0-9]*):([1-9][0-9]*)', anchor) if isinstance(anchor, str) else None
                if not match:
                    errors.append(label + ': anchor must be a supplied source ID such as S1:20')
                    continue
                file_index, number = map(int, match.groups())
                if file_index > len(task['allowed_files']):
                    errors.append(label + ': source ID refers to an unknown file')
                    continue
                name = task['allowed_files'][file_index - 1]
                path = (repo / name).resolve()
                if not path.is_relative_to(repo.resolve()) or not path.is_file():
                    errors.append(label + ': source ID file is unavailable or outside repository')
                    continue
                try:
                    lines = path.read_text().splitlines()
                except (OSError, UnicodeError) as error:
                    errors.append(label + ': cannot read source ID file: ' + str(error))
                    continue
                if number > len(lines) or not lines[number - 1].strip():
                    errors.append(label + ': source ID refers to a missing or blank line')
                    continue
                if 'file' in item and item['file'] != name:
                    errors.append(label + ': supplied file contradicts source ID')
                    continue
                if 'quote' in item and (not isinstance(item['quote'], str) or item['quote'] not in lines[number - 1]):
                    errors.append(label + ': supplied quote contradicts source ID')
                    continue
                if 'line' in item:
                    item['model_line'] = item['line']
                item.update(file=name, line=number, quote=lines[number - 1])
                continue
            name, quote = item.get('file'), item.get('quote')
            if name not in task['allowed_files']:
                errors.append(label + ': evidence requires an allowed file')
                continue
            if not isinstance(quote, str) or not quote.strip() or '\n' in quote or '\r' in quote:
                errors.append(label + ': quote must be a nonempty exact single-line substring')
                continue
            path = (repo / name).resolve()
            if not path.is_relative_to(repo.resolve()) or not path.is_file():
                errors.append(label + ': evidence file is unavailable or outside repository')
                continue
            try:
                lines = path.read_text().splitlines()
            except (OSError, UnicodeError) as error:
                errors.append(label + ': cannot read evidence file: ' + str(error))
                continue
            matches = [number for number, line in enumerate(lines, 1) if quote in line]
            if not matches:
                errors.append(label + ': exact quote not found in ' + name)
            elif len(matches) > 1:
                errors.append(label + ': ambiguous quote in ' + name + '; use a longer unique quote')
            else:
                if 'line' in item:
                    item['model_line'] = item['line']
                item['line'] = matches[0]

    for index, finding in enumerate(resolved['findings']):
        if not isinstance(finding.get('failure_case'), str) or not finding['failure_case'].strip():
            errors.append(f'findings[{index}]: concrete failure_case is required')
        citations(finding.get('evidence'), f'findings[{index}].evidence')
    coverage = resolved.get('coverage')
    if not isinstance(coverage, list):
        errors.append('Review requires acceptance-criterion coverage')
        coverage = []
    expected = set(range(1, len(task['acceptance_criteria']) + 1))
    seen = set()
    for index, item in enumerate(coverage):
        if not isinstance(item, dict):
            errors.append(f'coverage[{index}]: coverage must be an object')
            continue
        criterion = item.get('criterion')
        if type(criterion) is not int or criterion not in expected or criterion in seen:
            errors.append(f'coverage[{index}]: criterion must be a unique integer from 1 to {len(expected)}')
        else:
            seen.add(criterion)
        if not isinstance(item.get('reason'), str) or not item['reason'].strip():
            errors.append(f'coverage[{index}]: reasoning is required')
        citations(item.get('evidence'), f'coverage[{index}].evidence')
    if seen != expected:
        errors.append('Missing acceptance criteria: ' + ', '.join(map(str, sorted(expected - seen))))
    if errors:
        raise ValueError('Review validation errors:\n- ' + '\n- '.join(errors))
    return resolved


def model_environment(config):
    env = dict(os.environ)
    if config.get('node_bin'):
        env['PATH'] = config['node_bin'] + os.pathsep + env['PATH']
    # Read only explicitly named literal exports; never execute shell startup code.
    env_file = config.get('environment_file')
    if env_file:
        allowed = set(config.get('environment_keys', []))
        for line in Path(env_file).expanduser().read_text().splitlines():
            words = shlex.split(line, comments=True)
            if len(words) == 2 and words[0] == 'export' and '=' in words[1]:
                key, value = words[1].split('=', 1)
                if key in allowed:
                    if '$' in value or '`' in value:
                        raise ValueError('Environment exports must be literal values')
                    env[key] = value
    if config.get('local_only'):
        endpoint = urlsplit(env.get('ANTHROPIC_BASE_URL', ''))
        try:
            local = endpoint.hostname == 'localhost' or ipaddress.ip_address(endpoint.hostname).is_private
        except ValueError:
            local = False
        if endpoint.scheme not in {'http', 'https'} or not local or endpoint.username or endpoint.password:
            raise ValueError('Local-only runs require an explicit private-IP or localhost inference endpoint')
        if not env.get('ANTHROPIC_MODEL'):
            raise ValueError('Local-only runs require an explicit ANTHROPIC_MODEL')
        for key in ('CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY',
                    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
            env.pop(key, None)
        env['ANTHROPIC_API_KEY'] = env.get('ANTHROPIC_AUTH_TOKEN', 'local-inference')
        env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'] = '1'
    env.pop('CLAUDECODE', None)
    return env


class Runner:
    def __init__(self, config, task, run_dir):
        self.config, self.task, self.directory = config, task, run_dir
        self.repo = Path(config['repository']).resolve()
        self.env = model_environment(config)
        self.base = snapshot(self.repo)
        self.head = git(self.repo, 'rev-parse', 'HEAD')
        self.index = git(self.repo, 'diff', '--cached', '--binary')
        self.dialogue = self.directory / 'dialogue.md'
        if not self.dialogue.exists():
            self.dialogue.write_text('# ' + task['id'] + ': ' + task['title'] + '\n')
        self.guide = (ROOT / config['guide']).read_text()
        if config.get('test_guide'):
            self.guide += '\n\n' + (ROOT / config['test_guide']).read_text()
        self.latest_review = {'findings': []}
        self.latest_implementation = ''
        self.latest_checks = []
        self.review_attempt = 1
        self.control_files = [p for p in ROOT.rglob('*') if p.is_file()
                              and not any(part in ('runs', '__pycache__', '.git') for part in p.relative_to(ROOT).parts)]
        self.control_files += [Path(config[k]) for k in ('guide', 'test_guide') if config.get(k) and Path(config[k]).is_absolute()]
        # Protect external task/config snapshots and explicit script executables too.
        self.control_files += [self.directory / name for name in ('config.json', 'task.json')
                               if (self.directory / name).is_file()]
        for check in config.get('checks', []) + config.get('acceptance_checks', []):
            for arg in check['argv']:
                candidate = Path(arg)
                if candidate.is_absolute() and candidate.is_file() and not candidate.resolve().is_relative_to(self.repo):
                    self.control_files.append(candidate.resolve())
        self.control_files += [Path(name) for name in config.get('control_files', [])]
        self.controls = {str(p): digest(p.read_bytes()) for p in self.control_files}
        if not (self.directory / 'control-hashes.json').exists():
            (self.directory / 'control-hashes.json').write_text(json.dumps(self.controls, indent=2))
            (self.directory / 'runner-source.py').write_text(Path(__file__).read_text())
            (self.directory / 'repository-guide.md').write_text(self.guide)

    def context(self, persona):
        handoff = {'open_findings': self.latest_review.get('findings', []), 'checks': self.latest_checks}
        if persona in {'reviewer', 'adjudicator'} and handoff['open_findings']:
            handoff['implementer_response_to_findings'] = getattr(self, 'latest_implementation', '')[:6000]
            handoff['response_instruction'] = 'Unverified implementer response: check its evidence against source and deterministic results. Resolve rejected findings when the premise is false.'
        # Full dialogue remains available for audit, but prior verdicts and agent
        # narratives are not injected into a fresh review as presumed facts.
        value = 'CURRENT HANDOFF\n' + json.dumps(handoff, indent=2)
        if persona in {'reviewer', 'adjudicator'}:
            sources = []
            for file_index, name in enumerate(self.task['allowed_files'], 1):
                path = self.repo / name
                if path.is_file():
                    lines = path.read_text().splitlines()
                    sources.append(f'S{file_index} = {name}\n' + '\n'.join(f'[S{file_index}:{i}] {i}: {line}' for i, line in enumerate(lines, 1)))
            packet = '\n\n'.join(sources)
            if len(packet.encode()) > self.config.get('max_review_source_bytes', 60000):
                raise ValueError('Review source packet exceeds budget; narrow the task')
            value += '\n\nCOMPLETE CURRENT SOURCE (numbered)\n' + packet
        return value

    def state(self, status, **details):
        data = {'task': self.task['id'], 'status': status,
                'updated_at': datetime.now(timezone.utc).isoformat(), **details}
        temporary = self.directory / 'state.tmp'
        temporary.write_text(json.dumps(data, indent=2) + '\n')
        temporary.replace(self.directory / 'state.json')
        print(json.dumps(data), flush=True)

    def append(self, heading, body):
        with self.dialogue.open('a') as log:
            log.write('\n## ' + heading + '\n\n' + body + '\n')

    def guard(self):
        if any(not Path(p).is_file() or digest(Path(p).read_bytes()) != value for p, value in self.controls.items()):
            raise RuntimeError('Orchestrator controls changed during run')
        if git(self.repo, 'rev-parse', 'HEAD') != self.head or git(self.repo, 'diff', '--cached', '--binary') != self.index:
            raise RuntimeError('Agent changed HEAD or Git index')
        unexpected = changed(self.base, snapshot(self.repo)) - set(self.task['allowed_files'])
        if unexpected:
            raise RuntimeError('Out-of-scope edits: ' + ', '.join(sorted(unexpected)))

    def time_limit(self, configured):
        remaining = self.config.get('deadline_epoch', float('inf')) - time.time()
        if remaining <= 0:
            raise TimeoutError('Task/overnight deadline reached')
        return min(configured, remaining)

    def checks(self, prefix):
        before = snapshot(self.repo)
        results = []
        checks = self.config['checks'] + (self.config.get('acceptance_checks', []) if prefix != 'baseline' else [])
        for check in checks:
            output = self.directory / (prefix + '-' + check['name'] + '.log')
            started = time.monotonic()
            code = run_process(check['argv'], self.repo / check['cwd'], output,
                               self.time_limit(self.config['check_timeout_seconds']), self.env)
            results.append({'name': check['name'], 'exit_code': code, 'log': output.name,
                            'seconds': round(time.monotonic() - started, 2),
                            **({'failure_output': output.read_text(errors='replace')[-2000:]} if code else {})})
        if snapshot(self.repo) != before:
            raise RuntimeError('Verification mutated repository files')
        (self.directory / (prefix + '-checks.json')).write_text(json.dumps(results, indent=2))
        self.latest_checks = results
        self.append(prefix + ' verification', json.dumps(results, indent=2))
        return all(r['exit_code'] == 0 for r in results), results

    def invoke(self, persona, round_number, extra):
        template = (ROOT / 'prompts' / (persona + '.md')).read_text()
        if self.config.get('local_only'):
            template += '\nThis is an offline local-only batch. Do not invoke hosted models, other agent CLIs, image generation, paid APIs, network services, or deployment commands. Use mocks and deterministic local tests. Leave any unresolved design question in the report.'
        prompt = '\n\n'.join([template, 'REPOSITORY GUIDE\n' + self.guide,
                               'APPROVED TASK\n' + json.dumps(self.task, indent=2),
                               self.context(persona), extra])
        stem = f'round-{round_number}-{persona}'
        if persona in {'reviewer', 'adjudicator'} and self.review_attempt > 1:
            stem += f'-attempt-{self.review_attempt}'
        (self.directory / (stem + '-prompt.md')).write_text(prompt)
        tools = 'Read,Glob,Grep' if persona in {'reviewer', 'adjudicator'} else 'Read,Glob,Grep,Edit,Write,Bash'
        argv = [self.config['claude'], '-p', '--output-format', 'json', '--no-session-persistence',
                '--tools', tools, '--allowedTools', tools, '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}']
        if self.config.get('local_only'):
            argv += ['--bare', '--setting-sources', '', '--disable-slash-commands',
                     '--model', self.env['ANTHROPIC_MODEL']]
        log = self.directory / (stem + '.json')
        self.state(persona, round=round_number)
        process_options = {}
        if self.config.get('local_only'):
            probe_inference(self.env, self.time_limit(5))
            failures = 0

            def heartbeat(remaining):
                nonlocal failures
                if remaining <= 0:
                    return
                try:
                    probe_inference(self.env, min(5, remaining), active=True)
                except InferenceUnavailable:
                    failures += 1
                    if failures >= 2:
                        raise
                else:
                    failures = 0

            process_options['heartbeat'] = heartbeat
        code = run_process(argv, self.repo, log, self.time_limit(self.config['invocation_timeout_seconds']),
                           self.env, prompt, **process_options)
        try:
            envelope = parse_envelope(log.read_text())
        except ValueError:
            if code:
                raise RuntimeError(f'{persona} exited {code}; see {log.name}') from None
            raise
        result = envelope.get('result')
        if self.config.get('local_only') and envelope.get('is_error') and isinstance(result, str):
            if any(token in result.lower() for token in ('econnrefused', 'econnreset', 'request timed out',
                                                          'connection refused', 'connection reset')):
                raise InferenceUnavailable(f'{persona} lost local inference; see {log.name}')
        if code or envelope.get('is_error') or not isinstance(result, str):
            raise RuntimeError(f'{persona} failed; see {log.name}')
        report = envelope['result']
        with (self.directory / 'invocations.jsonl').open('a') as metrics:
            metrics.write(json.dumps({'round': round_number, 'persona': persona,
                                      'attempt': self.review_attempt if persona in {'reviewer', 'adjudicator'} else 1,
                                      'duration_ms': envelope.get('duration_ms'),
                                      'turns': envelope.get('num_turns'), 'usage': envelope.get('usage')}) + '\n')
        (self.directory / (stem + '.md')).write_text(report)
        self.guard()
        return report

    def accept(self, round_number, review_count, before_review, current_patch):
        modifications = changed(self.base, snapshot(self.repo))
        missing = set(self.task.get('required_changed_files', [])) - modifications
        if not modifications or missing:
            raise RuntimeError('Required implementation deliverables missing at acceptance')
        passed, _ = self.checks('final')
        self.guard()
        if not passed or snapshot(self.repo) != before_review or patch(self.repo) != current_patch:
            raise RuntimeError('Final checks failed or reviewed content changed')
        (self.directory / 'accepted.patch').write_bytes(current_patch)
        self.state('accepted', round=round_number, reviews=review_count,
                   patch_sha256=digest(current_patch), base_commit=self.head.decode().strip(), committed=False)
        return 0

    def escalate(self, round_number, review_count, reason):
        before = snapshot(self.repo)
        packet = {'task': self.task, 'repository': str(self.repo),
                  'patch_sha256': digest(patch(self.repo)),
                  'findings': self.latest_review['findings'],
                  'implementer_response': self.latest_implementation[:6000],
                  'checks': self.latest_checks,
                  'source_hashes': {name: before.get(name) for name in self.task['allowed_files']},
                  'reason': reason}
        (self.directory / 'parent-packet.json').write_text(json.dumps(packet, indent=2))
        checkpoint = {'round': round_number, 'reviews': review_count, 'base': self.base,
                      'head': self.head.decode(), 'index_hex': self.index.hex(),
                      'snapshot': before, 'patch_sha256': packet['patch_sha256'],
                      'review': self.latest_review, 'implementation': self.latest_implementation,
                      'checks': self.latest_checks, 'controls': self.controls,
                      'config_sha256': digest(json.dumps(self.config, sort_keys=True).encode()),
                      'task_sha256': digest(json.dumps(self.task, sort_keys=True).encode())}
        (self.directory / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2))
        self.state('parent_required', round=round_number, reviews=review_count, reason=reason)
        return 2

    def restore(self, decision):
        from dispute_review import resolve_parent
        saved = json.loads((self.directory / 'checkpoint.json').read_text())
        for name, value in [('config', self.config), ('task', self.task)]:
            if digest(json.dumps(value, sort_keys=True).encode()) != saved[name + '_sha256']:
                raise ValueError('Resume contract changed: ' + name)
        if json.loads(json.dumps(snapshot(self.repo))) != saved['snapshot']:
            raise ValueError('Resume source changed since escalation')
        self.controls = saved['controls']
        self.head, self.index = saved['head'].encode(), bytes.fromhex(saved['index_hex'])
        self.base = {k: tuple(v) if isinstance(v, list) else v for k, v in saved['base'].items()}
        self.guard()
        packet = json.loads((self.directory / 'parent-packet.json').read_text())
        if (packet['patch_sha256'] != saved['patch_sha256'] or
                packet['findings'] != saved['review']['findings'] or
                packet['task'] != self.task or Path(packet['repository']).resolve() != self.repo):
            raise ValueError('Resume packet changed')
        result = resolve_parent(packet, decision)
        (self.directory / 'parent-decision.json').write_text(json.dumps(result, indent=2))
        self.latest_review = saved['review']
        self.latest_implementation, self.latest_checks = saved['implementation'], saved['checks']
        remaining = [f for f in self.latest_review['findings']
                     if result['resolutions'][f['id']]['decision'] != 'withdrawn']
        self.latest_review['findings'] = remaining
        self.latest_review['verdict'] = 'request_changes' if remaining else 'approve'
        self.append('Hosted parent decision', json.dumps(result, indent=2))
        return saved, result

    def execute(self, decision=None):
        if decision is not None:
            saved, result = self.restore(decision)
            if result['status'] in ('unresolved', 'blocked_checks'):
                self.state('parent_required', reason=result['status'])
                return 2
            review_count = saved['reviews']
            if not self.latest_review['findings'] and review_count >= self.config['min_review_rounds']:
                return self.accept(saved['round'], review_count, snapshot(self.repo), patch(self.repo))
            start_round = saved['round'] + 1
        else:
            if git(self.repo, 'status', '--porcelain').strip():
                raise RuntimeError('Target must start with a clean Git working tree')
            self.state('baseline')
            passed, _ = self.checks('baseline')
            if not passed:
                self.state('baseline_failed')
                return 1
            review_count, start_round = 0, 1
        for round_number in range(start_round, self.config['max_rounds'] + 1):
            previous_findings = {f['id'] for f in getattr(self, 'latest_review', {'findings': []})['findings']}
            report = self.invoke('implementer', round_number, 'Implement or address the latest review. Stop after this task.')
            self.latest_implementation = report
            self.append(f'Round {round_number}: implementer', report)
            current_patch = patch(self.repo)
            (self.directory / f'round-{round_number}.patch').write_bytes(current_patch)
            modifications = changed(self.base, snapshot(self.repo))
            if not modifications:
                raise RuntimeError('No implementation changes produced')
            missing = set(self.task.get('required_changed_files', [])) - modifications
            if missing:
                self.append('Missing deliverables', 'Required changes missing: ' + ', '.join(sorted(missing)))
                continue
            self.state('verification', round=round_number)
            passed, checks = self.checks(f'round-{round_number}')
            self.guard()
            if not passed:
                self.append(f'Round {round_number}: repair required',
                            'Mandatory checks failed. Inspect these logs and fix the cause:\n' +
                            '\n'.join(str(self.directory / r['log']) for r in checks if r['exit_code']))
                continue
            before_review = snapshot(self.repo)
            error = ''
            for attempt in range(1, self.config.get('review_output_attempts', 2) + 1):
                self.review_attempt = attempt
                review_text = self.invoke('reviewer', round_number,
                    'Review this exact diff against the COMPLETE CURRENT SOURCE above:\n' +
                    current_patch.decode(errors='replace') + error)
                if snapshot(self.repo) != before_review:
                    raise RuntimeError('Reviewer mutated repository files')
                try:
                    review = parse_review(review_text)
                    review = validate_review_evidence(review, self.repo, self.task)
                    break
                except ValueError as failure:
                    self.append(f'Round {round_number}: invalid review output', str(failure))
                    if attempt == self.config.get('review_output_attempts', 2):
                        return self.escalate(round_number, review_count, 'Review output retries exhausted: ' + str(failure))
                    error = '\nOUTPUT VALIDATION ERROR: ' + str(failure) + '\nReturn a corrected review addressing ALL errors, using source IDs supplied in brackets, such as S1:20.'
            (self.directory / f'round-{round_number}-review-resolved.json').write_text(json.dumps(review, indent=2))
            self.latest_review = review
            review_count += 1
            self.append(f'Round {round_number}: reviewer', json.dumps(review, indent=2))
            repeated = previous_findings & {f['id'] for f in review['findings']}
            if repeated and self.config.get('dispute_escalation', False):
                from dispute_review import opinion
                self.opinion_round = round_number
                try:
                    review, decisions = opinion(self, 'adjudicator', review['findings'], before_review)
                except ValueError as failure:
                    return self.escalate(round_number, review_count, str(failure))
                self.latest_review = review
                if any(row['decision'] != 'withdrawn' for row in decisions.values()):
                    return self.escalate(round_number, review_count, 'Finding persists after fresh local opinion')
            if review['verdict'] == 'approve' and review_count >= self.config['min_review_rounds']:
                return self.accept(round_number, review_count, before_review, current_patch)
            if review['verdict'] == 'approve':
                self.append('Additional experimental review round',
                            'Approval recorded. Run a fresh implementation response and second review; do not invent changes.')
        if self.config.get('dispute_escalation', False) and self.latest_review['findings']:
            return self.escalate(self.config['max_rounds'], review_count, 'Round limit reached with open findings')
        self.state('unresolved', reason='Round limit reached; changes retained for inspection')
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/entourage.json')
    parser.add_argument('--task', default='tasks/E001.json')
    parser.add_argument('--run-dir', help='Explicit artifact directory for the reusable CLI')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--decision', help='Hosted parent decision JSON for a pending escalation')
    args = parser.parse_args()
    if args.resume and (not args.run_dir or not args.decision):
        parser.error('--resume requires --run-dir and --decision')
    config = json.loads((ROOT / args.config).read_text())
    task = json.loads((ROOT / args.task).read_text())
    # Low-level entry point also enforces the reusable CLI contract.
    from orchestrator import validate
    try:
        validate(config, task)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    if not 1 <= config['min_review_rounds'] <= config['max_rounds']:
        parser.error('Require 1 <= min_review_rounds <= max_rounds')
    repo = Path(config['repository']).resolve()
    for name in task['allowed_files']:
        if Path(name).is_absolute() or '..' in Path(name).parts or not (repo / name).resolve().is_relative_to(repo):
            parser.error('Allowed files must stay within target repository')
    # Cross-process lock lives in .git, outside files the implementation may edit.
    common = Path(os.fsdecode(git(repo, 'rev-parse', '--git-common-dir')).strip())
    if not common.is_absolute():
        common = repo / common
    with (common / 'autonomous-loop.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another runner owns this repository')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        directory = Path(args.run_dir).resolve() if args.run_dir else ROOT / 'runs' / (stamp + '-' + task['id'])
        if args.resume:
            if json.loads((directory / 'state.json').read_text())['status'] != 'parent_required':
                parser.error('Only parent_required runs may resume')
            if json.loads((directory / 'config.json').read_text()) != config or json.loads((directory / 'task.json').read_text()) != task:
                parser.error('Saved run contract changed')
        else:
            directory.mkdir(parents=True, exist_ok=False)
        (directory / 'config.json').write_text(json.dumps(config, indent=2))
        (directory / 'task.json').write_text(json.dumps(task, indent=2))
        runner = Runner(config, task, directory)
        print('Run artifacts: ' + str(directory), flush=True)
        try:
            return runner.execute(json.loads(Path(args.decision).read_text()) if args.resume else None)
        except (Exception, KeyboardInterrupt) as error:
            try:
                (directory / 'interrupted.patch').write_bytes(patch(repo))
            finally:
                runner.state('inference_unavailable' if isinstance(error, InferenceUnavailable) else 'stopped',
                             reason=str(error) or type(error).__name__)
            return 1


if __name__ == '__main__':
    sys.exit(main())
