"""Dependency-free unit tests for optional identity reads (no network access)."""
import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

SOURCE = Path(__file__).resolve().parents[1] / 'custom_components/htha/coordinator.py'
tree = ast.parse(SOURCE.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_async_read_metadata')
namespace = {'_LOGGER': logging.getLogger(__name__)}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), 'exec'), namespace)
read_metadata = namespace['_async_read_metadata']

class MetadataTests(unittest.IsolatedAsyncioTestCase):
    def coordinator(self):
        return SimpleNamespace(_metadata_attempted=False, serial_number=None, sw_version=None,
            _heatpump=SimpleNamespace(get_serial_number_async=AsyncMock(return_value=123456),
                get_version_async=AsyncMock(return_value=('3.0.20', 273))))

    async def test_identity_cached_once(self):
        coordinator = self.coordinator()
        async with asyncio.Lock():
            await read_metadata(coordinator)
            await read_metadata(coordinator)
        self.assertEqual(coordinator.serial_number, '123456')
        self.assertEqual(coordinator.sw_version, '3.0.20')
        coordinator._heatpump.get_serial_number_async.assert_awaited_once()
        coordinator._heatpump.get_version_async.assert_awaited_once()

    async def test_serial_failure_does_not_skip_firmware(self):
        coordinator = self.coordinator()
        coordinator._heatpump.get_serial_number_async.side_effect = OSError('unsupported')
        await read_metadata(coordinator)
        self.assertIsNone(coordinator.serial_number)
        self.assertEqual(coordinator.sw_version, '3.0.20')

    async def test_both_failures_are_nonfatal_and_not_retried(self):
        coordinator = self.coordinator()
        coordinator._heatpump.get_serial_number_async.side_effect = OSError('unsupported')
        coordinator._heatpump.get_version_async.side_effect = ValueError('invalid response')
        await read_metadata(coordinator)
        await read_metadata(coordinator)
        self.assertIsNone(coordinator.serial_number)
        self.assertIsNone(coordinator.sw_version)
        coordinator._heatpump.get_version_async.assert_awaited_once()

if __name__ == '__main__':
    unittest.main()
