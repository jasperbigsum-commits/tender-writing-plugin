"""Offline public-package preflight, NOT an official schema validator or approval.

Never contacts a service or submits a package. Portal scans, identity, policies,
URL content and host behavior must still be verified independently.
"""
import argparse
import json
from pathlib import PurePosixPath
import struct
import unicodedata
from urllib.parse import urlsplit
import zipfile

URL_FIELDS = ('websiteURL', 'supportURL', 'privacyPolicyURL', 'termsOfServiceURL')


def inspect_archive(archive):
    errors = []
    pending = ['verified publisher identity and policy attestations',
               'official skill safety/security scans', 'installation and six-skill smoke test in target host',
               'owner country targeting and commerce declarations',
               'public English listing/localization review before submission']
    recommended = []
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            errors.append('duplicate ZIP entries')
        if not names or any(n.startswith('/') or '\\' in n or '..' in PurePosixPath(n).parts for n in names):
            errors.append('unsafe or empty archive')
        roots = {n.split('/')[0] for n in names}
        if len(roots) != 1:
            errors.append('expected one plugin root')
        if errors:
            return _report(errors, pending, recommended)
        root = next(iter(roots))
        if any(n.endswith(('/mcp.json', '/.mcp.json')) for n in names):
            errors.append('MCP configuration requires a separate remote/local MCP review; skills-only preflight is insufficient')
        if f'{root}/plugin.json' not in names:
            return _report(['missing portable manifest'], pending, recommended)
        m = json.loads(z.read(f'{root}/plugin.json'))
        interface = m.get('extensions', {}).get('com.openai', {}).get('interface', {})
        for name in names:
            if name.endswith('/.app.json'):
                errors.append('public upload must not contain .app.json')
            if name.endswith('/plugin.json'):
                doc = json.loads(z.read(name))
                if doc.get('apps') is not None or doc.get('extensions', {}).get('com.openai', {}).get('apps') is not None:
                    errors.append(f'forbidden app binding: {name}')
        for field, limit in [('displayName', 30), ('shortDescription', 30), ('longDescription', 4000)]:
            value = interface.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                errors.append(f'invalid {field}')
            elif field != 'longDescription' and any(c in value for c in '\r\n\u2028\u2029'):
                errors.append(f'multiline {field}')
        prompts = interface.get('defaultPrompt', [])
        if isinstance(prompts, str):
            prompts = [prompts]
        if not isinstance(prompts, list) or len(prompts) > 3:
            errors.append('invalid starter prompts')
        else:
            normalized = []
            for prompt in prompts:
                if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 128 or any(c in prompt for c in '\r\n\u2028\u2029@'):
                    errors.append('invalid starter prompt')
                else:
                    normalized.append(' '.join(unicodedata.normalize('NFKC', prompt).split()))
            if len(normalized) != len(set(normalized)):
                errors.append('duplicate normalized starter prompts')
        for key, minimum in [('logo', 256), ('composerIcon', 48)]:
            path = interface.get(key, '')
            parts = PurePosixPath(path).parts
            if not path or path.startswith('/') or '..' in parts or '\\' in path:
                errors.append(f'unsafe {key} path')
                continue
            member = root + '/' + str(PurePosixPath(path))
            if member not in names:
                errors.append(f'missing {key}')
                continue
            data = z.read(member)
            if len(data) > 5 * 1024 * 1024 or len(data) < 33 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
                errors.append(f'{key} must be a PNG up to 5 MiB')
                continue
            w, h = struct.unpack('>II', data[16:24])
            if w != h or w < minimum or w > 4096:
                errors.append(f'invalid {key} dimensions')
        for field in URL_FIELDS:
            value = interface.get(field)
            if not value:
                recommended.append(f'{field}: not supplied; optional for skills-only ZIP, required for remote MCP')
                continue
            try:
                u = urlsplit(value)
                valid = isinstance(value, str) and len(value) <= 1024 and u.scheme == 'https' and u.hostname and not u.username and not u.password and not any(c.isspace() for c in value)
            except (TypeError, ValueError):
                valid = False
            if not valid:
                errors.append(f'invalid HTTPS {field}')
            else:
                pending.append(f'{field}: public access and purpose-specific content unverified')
        if not interface.get('developerName'):
            pending.append('developerName: populate from selected verified identity, never invent')
    return _report(errors, pending, recommended)


def _report(errors, pending, recommended):
    return {'package_errors': errors, 'public_submission_ready': False,
            'status': 'blocked_local_validation' if errors else 'pending_external_review',
            'external_checks': pending, 'recommended_listing_materials': recommended,
            'submitted': False, 'note': 'Offline checks are not OpenAI approval. No network or portal actions performed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    args = parser.parse_args()
    result = inspect_archive(args.archive)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['package_errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
