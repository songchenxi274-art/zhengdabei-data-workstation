from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_desk.audit import AuditLogger


class AuditTests(unittest.TestCase):
    def test_audit_record_contains_metadata_only(self):
        path = ROOT / "work" / f"audit_{uuid4().hex}.jsonl"
        try:
            logger = AuditLogger(path)
            logger.record(
                "online_authorization",
                outcome="approved",
                data_level="D1",
                provider="provider-a",
                fingerprint="abc123",
            )
            record = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(record["event"], "online_authorization")
            self.assertNotIn("prompt", record)
            self.assertNotIn("data", record)
        finally:
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
