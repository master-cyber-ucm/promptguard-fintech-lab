"""Un diff con texto histórico no UTF-8 debe conservar su huella sin romper el run."""
import hashlib
import subprocess
import sys

import provenance


def test_diff_no_utf8_preserva_bytes_y_huella(monkeypatch):
    raw_diff = b'diff --git a/notas.txt b/notas.txt\n+\x93resultado\x94\n'
    real_run = subprocess.run

    def git_output(command, **kwargs):
        responses = {
            ('rev-parse', 'HEAD'): b'commit-test\n',
            ('rev-parse', '--abbrev-ref', 'HEAD'): b'main\n',
            ('status', '--porcelain'): b' M notas.txt\n',
            ('diff', 'HEAD'): raw_diff,
        }
        output = responses[tuple(command[1:])]
        return real_run(
            [sys.executable, '-c', f'import sys; sys.stdout.buffer.write({output!r})'],
            **kwargs,
        )

    for name in ('GIT_COMMIT', 'GIT_BRANCH', 'GIT_DIRTY', 'GIT_DIRTY_FILES'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(provenance.subprocess, 'run', git_output)
    result = provenance.git_provenance()
    assert result['commit'] == 'commit-test'
    assert result['dirty'] is True
    assert result['diff_sha256'] == hashlib.sha256(raw_diff.strip()).hexdigest()[:16]
