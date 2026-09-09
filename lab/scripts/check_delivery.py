#!/usr/bin/env python3
"""Comprueba el anexo y los recursos de entrega, sin Docker ni dependencias externas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def check_evidence() -> list[str]:
    errors = []
    folder = ROOT / 'docs' / 'evidencias'
    manifest = json.loads((folder / 'manifest.json').read_text())
    archive = folder / manifest['archive']
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archive_sha256']:
        errors.append('El SHA-256 del anexo no coincide con el manifiesto')
    with zipfile.ZipFile(archive) as bundle:
        expected = {item['path'] for item in manifest['files']}
        if set(bundle.namelist()) != expected or len(bundle.namelist()) != len(expected):
            errors.append('El inventario del anexo no coincide con el manifiesto')
        for item in manifest['files']:
            if item['path'] not in bundle.namelist():
                continue
            content = bundle.read(item['path'])
            if len(content) != item['bytes'] or hashlib.sha256(content).hexdigest() != item['sha256']:
                errors.append(f"Evidencia alterada: {item['path']}")
    return errors


def check_payloads() -> list[str]:
    errors = []
    fixtures = ROOT / 'lab' / 'backend' / 'tests' / 'fixtures'
    documents = []
    for fixture in fixtures.rglob('*.yaml'):
        match = re.search(r'^document:\s*([^\n#]+)', fixture.read_text(), re.MULTILINE)
        if not match:
            continue
        name = match.group(1).strip().strip('\"\'')
        documents.append(name)
        if not (ROOT / 'lab' / 'payloads' / name).is_file():
            errors.append(f'Documento ausente: {name} ({fixture.relative_to(ROOT)})')
    if not documents:
        errors.append('No se ha encontrado ninguna fixture documental')
    return errors


def check_links() -> list[str]:
    errors = []
    paths = list(ROOT.glob('*.md')) + list((ROOT / 'docs').rglob('*.md'))
    paths += [ROOT / 'lab' / 'README.md', ROOT / 'lab' / 'payloads' / 'README.md',
              ROOT / 'lab' / 'redteam-agent' / 'README.md',
              ROOT / 'lab' / 'redteam-agent' / 'sources' / 'README.md',
              ROOT / 'lab' / 'backend' / 'tests' / 'fixtures' / 'README.md']
    for path in paths:
        text = re.sub(r'```.*?```', '', path.read_text(), flags=re.DOTALL)
        for match in re.finditer(r'\]\(([^\s)]+)\)', text):
            target = match.group(1).strip('<>')
            if target.startswith('#') or urlsplit(target).scheme:
                continue
            target_path = unquote(target.split('#', 1)[0])
            if target_path and not (path.parent / target_path).exists():
                errors.append(f'{path.relative_to(ROOT)}: enlace ausente: {target}')
    return errors


def main() -> int:
    errors = check_evidence() + check_payloads() + check_links()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Entrega verificada: anexo íntegro, documentos de fixtures presentes y enlaces locales válidos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
