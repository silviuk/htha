"""Regression: every platform sharing the pump must publish identical metadata."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/htha'

class DeviceInfoTests(unittest.TestCase):
    def info(self, filename, model):
        tree = ast.parse((ROOT / filename).read_text())
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == 'DeviceInfo')
        return eval(compile(ast.Expression(call), filename, 'eval'), {
            'DeviceInfo': lambda **kw: kw, 'DOMAIN': 'htha',
            'config_entry': SimpleNamespace(entry_id='test', options={'model': model}),
            'coordinator': SimpleNamespace(host='example.invalid', port=9999,
                serial_number='100204', sw_version='2.03N')})

    def test_all_platforms_use_same_configured_identity(self):
        for filename in ['entity.py', 'switch.py', 'button.py', 'datetime.py']:
            with self.subTest(filename=filename):
                info = self.info(filename, ' HP07S08W-S-WEB ')
                self.assertEqual(info['model'], 'HP07S08W-S-WEB')
                self.assertEqual(info['serial_number'], '100204')
                self.assertEqual(info['sw_version'], '2.03N')

    def test_all_platforms_keep_generic_fallback(self):
        for filename in ['entity.py', 'switch.py', 'button.py', 'datetime.py']:
            with self.subTest(filename=filename):
                self.assertEqual(self.info(filename, ' ')['model'], 'Heat Pump')

if __name__ == '__main__':
    unittest.main()
