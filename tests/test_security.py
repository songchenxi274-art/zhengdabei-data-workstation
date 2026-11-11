from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_desk.security import (
    AuthorizationError,
    DataLevel,
    DisclosureTracker,
    OnlineRequestPayload,
    build_authorized_request,
    evaluate_online_boundary,
    verify_authorized_payload,
)


class SecurityTests(unittest.TestCase):
    def payload(self) -> OnlineRequestPayload:
        return OnlineRequestPayload(
            provider="provider-a",
            model="model-a",
            request_url="https://provider.invalid/v1/chat/completions",
            system_prompt="system",
            user_prompt="user",
            data={"n": 20},
            attachments={"summary.txt": "abc123"},
            model_config={"temperature": 0, "max_tokens": 100},
        )

    def test_data_level_boundaries(self):
        self.assertTrue(evaluate_online_boundary(DataLevel.D0).allowed)
        self.assertTrue(evaluate_online_boundary(DataLevel.D1).allowed)
        self.assertFalse(evaluate_online_boundary(DataLevel.D1_R).allowed)
        self.assertTrue(
            evaluate_online_boundary(
                DataLevel.D1_R,
                exception_approved=True,
            ).allowed
        )
        self.assertFalse(evaluate_online_boundary(DataLevel.D2).allowed)
        self.assertFalse(evaluate_online_boundary(DataLevel.D3).allowed)

    def test_d1_requires_per_request_approval(self):
        with self.assertRaises(AuthorizationError):
            build_authorized_request(
                self.payload(),
                DataLevel.D1,
                user_approved=False,
            )
        authorized = build_authorized_request(
            self.payload(),
            DataLevel.D1,
            user_approved=True,
        )
        self.assertTrue(verify_authorized_payload(authorized, self.payload()))

    def test_fingerprint_changes_for_every_bound_field(self):
        payload = self.payload()
        changes = [
            replace(payload, provider="provider-b"),
            replace(payload, model="model-b"),
            replace(payload, request_url="https://other.invalid/v1"),
            replace(payload, system_prompt="system-b"),
            replace(payload, user_prompt="user-b"),
            replace(payload, data={"n": 21}),
            replace(payload, attachments={"summary.txt": "def456"}),
            replace(payload, model_config={"temperature": 1, "max_tokens": 100}),
        ]
        fingerprints = {payload.fingerprint()}
        fingerprints.update(change.fingerprint() for change in changes)
        self.assertEqual(len(fingerprints), len(changes) + 1)

    def test_actual_payload_must_match_authorized_payload(self):
        payload = self.payload()
        authorized = build_authorized_request(
            payload,
            DataLevel.D1,
            user_approved=True,
        )
        self.assertFalse(
            verify_authorized_payload(
                authorized,
                replace(payload, user_prompt="changed"),
            )
        )

    def test_disclosure_tracker_flags_repeated_or_d1r_requests(self):
        tracker = DisclosureTracker()
        self.assertFalse(tracker.register(DataLevel.D1))
        self.assertTrue(tracker.register(DataLevel.D1))
        self.assertTrue(tracker.register(DataLevel.D1_R))


if __name__ == "__main__":
    unittest.main()
