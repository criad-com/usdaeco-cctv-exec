"""A deferred or interrupted native gate must never manufacture acceptance."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

import check as gate
import tools_native_check as native


def missing_args(tmp_path, *extra):
    return native.argument_parser().parse_args([
        '--consumer', str(tmp_path / 'execcctv'),
        '--plugin-dir', str(tmp_path / 'plugin'), *extra,
    ])


def test_deferred_rows_survive_console_and_json(tmp_path, capsys):
    args = missing_args(tmp_path)
    report = native.Report()
    report.check('source regression', True)
    native.run_checks(args, report)
    native.write_report(tmp_path / 'report.json', report)
    assert report.finish() == 0
    output = capsys.readouterr().out
    assert '22 checks, 0 failed, 21 not run' in output
    assert output.count('NOT RUN  ') == 21
    data = json.loads((tmp_path / 'report.json').read_text())
    assert (data['total'], data['passed'], data['failed'], data['not_run']) == (22, 1, 0, 21)
    rows = data['checks'][1:]
    assert len({row['name'] for row in rows}) == 21
    assert {row['name'] for row in rows} == set(native.CHECK_NAMES)
    assert all(row['status'] == 'NOT RUN' and row['ok'] is None and row['detail'] for row in rows)
    assert all(not row for row in report.results[1:])


@pytest.mark.parametrize('present', ['consumer', 'plugin', 'nonexecutable'])
def test_partial_native_install_reports_the_missing_artifact(tmp_path, present):
    args = missing_args(tmp_path)
    if present in ('consumer', 'nonexecutable'):
        args.consumer.write_text('#!/bin/sh\nexit 0\n')
        if present == 'consumer':
            args.consumer.chmod(0o755)
    if present in ('plugin', 'nonexecutable'):
        args.plugin_dir.mkdir()
        (args.plugin_dir / 'plugInfo.json').write_text('{}')
    reason = native.unavailable_reason(args)
    expected = {'consumer': 'descriptor is missing', 'plugin': 'consumer is missing',
                'nonexecutable': 'consumer is not executable'}
    assert expected[present] in reason
    report = native.Report()
    native.run_checks(args, report)
    assert report.not_run_count == 21
    assert all(reason in row.detail for row in report.results)


def test_native_required_cli_exits_nonzero_and_writes_report(tmp_path):
    destination = tmp_path / 'required.json'
    done = subprocess.run([
        sys.executable, str(native.ROOT / 'tools_native_check.py'), '--native',
        '--consumer', str(tmp_path / 'absent'), '--plugin-dir', str(tmp_path / 'absent-plugin'),
        '--report', str(destination),
    ], text=True, capture_output=True)
    assert done.returncode == 1, done.stderr
    assert '22 checks, 1 failed, 21 not run' in done.stdout
    data = json.loads(destination.read_text())
    assert data['passed'] == 0 and data['failed'] == 1 and data['not_run'] == 21
    assert data['checks'][0]['status'] == 'FAIL'


def test_interrupted_native_gate_keeps_remaining_rows(tmp_path, monkeypatch):
    def stopped(args, report):
        report.check('manifest', True)
        raise RuntimeError('consumer could not load its runtime')
    monkeypatch.setattr(native, 'unavailable_reason', lambda args: '')
    monkeypatch.setattr(native, '_run_checks', stopped)
    report = native.Report()
    native.run_checks(missing_args(tmp_path), report)
    assert report.finish() == 1
    assert report.failed == 1 and report.not_run_count == 20
    assert all('failed prerequisite' in row.detail for row in report.results if row.ok is None)


def test_early_consumer_failure_keeps_baked_parity_not_run(tmp_path, monkeypatch):
    def failed(args, report):
        report.check('consumer run', False, 'consumer rejected the stage')
    monkeypatch.setattr(native, 'unavailable_reason', lambda args: '')
    monkeypatch.setattr(native, '_run_checks', failed)
    report = native.Report()
    native.run_checks(missing_args(tmp_path), report)
    assert report.failed == 1 and report.not_run_count == 20
    baked = next(row for row in report.results if row.name == 'lobby parity with the baked derived layer')
    assert baked.status == 'NOT RUN' and baked.detail


def test_missing_core_validators_fails_loudly(tmp_path, monkeypatch):
    original_import = gate.importlib.import_module
    def missing(name, *args, **kwargs):
        if name == 'usdAecoValidators':
            raise ModuleNotFoundError('usdAecoValidators is unavailable')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(gate.importlib, 'import_module', missing)
    report = native.Report()
    report.run('core validators', gate.core_validation, missing_args(tmp_path))
    assert report.failed == 1 and report.not_run_count == 0
    assert 'ModuleNotFoundError: usdAecoValidators' in report.results[0].detail


def test_gate_honours_cli_artifact_paths_and_writes_all_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'check_structure', lambda root: [])
    from usdaeco_check import Result
    monkeypatch.setattr(gate, 'link_check', lambda root: Result('links', True))
    monkeypatch.setattr(gate, 'dependency_versions', lambda args: (True, 'selected pins'))
    monkeypatch.setattr(gate, 'core_validation', lambda args: (True, 'loaded'))
    destination = tmp_path / 'gate.json'
    result = gate.main(['--consumer', str(tmp_path / 'missing-consumer'),
                        '--plugin-dir', str(tmp_path / 'missing-plugin'),
                        '--report', str(destination), '--native'])
    data = json.loads(destination.read_text())
    assert result == 1
    assert (data['passed'], data['failed'], data['not_run']) == (4, 1, 21)
    assert data['total'] == len(data['checks']) == 26
