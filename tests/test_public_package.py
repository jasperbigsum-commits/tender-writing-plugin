"""Public export regressions use copied, synthetic archives only."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_readiness', ROOT/'tools/public_readiness.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PublicPackageTests(unittest.TestCase):
    def inspect(self, change=None, extra=None):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder)/'test.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                for path in (ROOT/'tender-writing').rglob('*'):
                    if not path.is_file() or '__pycache__' in path.parts:
                        continue
                    data = path.read_bytes()
                    name = 'tender-writing/'+path.relative_to(ROOT/'tender-writing').as_posix()
                    if name == 'tender-writing/plugin.json' and change:
                        doc = json.loads(data); change(doc); data = json.dumps(doc).encode()
                    z.writestr(name, data)
                for name, data in (extra or {}).items():
                    z.writestr(name, data)
            return p.inspect_archive(archive)

    def test_current_package_is_not_claimed_approved(self):
        result = self.inspect()
        self.assertEqual([], result['package_errors'])
        self.assertFalse(result['public_submission_ready'])
        self.assertFalse(result['submitted'])
        self.assertEqual(4, len(result['recommended_listing_materials']))

    def test_hidden_apps_binding_rejected(self):
        result = self.inspect(extra={'tender-writing/legacy/plugin.json': '{"apps":"x"}'})
        self.assertTrue(any('app binding' in e for e in result['package_errors']))

    def test_app_file_rejected(self):
        self.assertTrue(self.inspect(extra={'tender-writing/.app.json': '{}'})['package_errors'])

    def test_traversal_rejected(self):
        self.assertTrue(self.inspect(extra={'tender-writing/../secret': 'x'})['package_errors'])

    def test_unicode_prompt_duplicates_rejected(self):
        result = self.inspect(lambda d: d['extensions']['com.openai']['interface'].update(defaultPrompt=['Ａ', 'A']))
        self.assertIn('duplicate normalized starter prompts', result['package_errors'])

    def test_asset_escape_rejected(self):
        result = self.inspect(lambda d: d['extensions']['com.openai']['interface'].update(logo='../icon.png'))
        self.assertIn('unsafe logo path', result['package_errors'])

    def test_svg_public_logo_rejected(self):
        result = self.inspect(lambda d: d['extensions']['com.openai']['interface'].update(logo='./assets/icon.svg'))
        self.assertTrue(any('PNG' in e for e in result['package_errors']))

    def test_url_credentials_rejected(self):
        result = self.inspect(lambda d: d['extensions']['com.openai']['interface'].update(websiteURL='https://user:pass@example.com'))
        self.assertIn('invalid HTTPS websiteURL', result['package_errors'])

    def test_compatibility_and_catalogs_synchronized(self):
        m=json.loads((ROOT/'tender-writing/plugin.json').read_text())
        c=json.loads((ROOT/'tender-writing/.codex-plugin/plugin.json').read_text())
        self.assertEqual(m['version'], c['version'])
        self.assertEqual(m['extensions']['com.openai']['interface'], c['interface'])
        self.assertEqual((ROOT/'.agents/plugins/marketplace.json').read_bytes(), (ROOT/'.claude-plugin/marketplace.json').read_bytes())
