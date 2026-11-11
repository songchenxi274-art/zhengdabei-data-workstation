from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


APP_VERSION = "0.1.0"
REQUEST_PROTOCOL_VERSION = "1"


class DataLevel(str, Enum):
    D0 = "D0"
    D1 = "D1"
    D1_R = "D1-R"
    D2 = "D2"
    D3 = "D3"

    @property
    def label(self) -> str:
        return {
            DataLevel.D0: "D0 公开",
            DataLevel.D1: "D1 一般聚合",
            DataLevel.D1_R: "D1-R 潜在披露聚合",
            DataLevel.D2: "D2 脱敏行级",
            DataLevel.D3: "D3 受限原始数据",
        }[self]


@dataclass(frozen=True)
class OnlineRequestPayload:
    provider: str
    model: str
    request_url: str
    system_prompt: str
    user_prompt: str
    data: Any
    attachments: dict[str, str]
    model_config: dict[str, Any]
    protocol_version: str = REQUEST_PROTOCOL_VERSION
    app_version: str = APP_VERSION

    def canonical_json(self) -> str:
        return json.dumps(
            asdict(self),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    requires_per_request_approval: bool
    requires_exception_approval: bool
    reason: str


@dataclass(frozen=True)
class AuthorizedOnlineRequest:
    payload: OnlineRequestPayload
    payload_json: str
    fingerprint: str
    data_level: DataLevel
    decision: AuthorizationDecision


@dataclass
class DisclosureTracker:
    total_requests: int = 0
    level_counts: dict[str, int] = field(default_factory=dict)

    def register(self, data_level: DataLevel) -> bool:
        prior_requests = self.total_requests
        self.total_requests += 1
        self.level_counts[data_level.value] = self.level_counts.get(data_level.value, 0) + 1
        return prior_requests > 0 or data_level is DataLevel.D1_R


class AuthorizationError(PermissionError):
    pass


def evaluate_online_boundary(
    data_level: DataLevel,
    *,
    exception_approved: bool = False,
) -> AuthorizationDecision:
    if data_level is DataLevel.D0:
        return AuthorizationDecision(True, False, False, "D0 公开内容允许在线发送。")
    if data_level is DataLevel.D1:
        return AuthorizationDecision(True, True, False, "D1 必须逐次授权。")
    if data_level is DataLevel.D1_R:
        return AuthorizationDecision(
            exception_approved,
            True,
            True,
            "D1-R 默认禁止；获批例外后仍需逐次授权。"
            if exception_approved
            else "D1-R 默认禁止，必须单独审批。",
        )
    if data_level is DataLevel.D2:
        return AuthorizationDecision(False, False, False, "V1 的 D2 仅允许本地处理。")
    return AuthorizationDecision(False, False, False, "V1 禁止在线发送 D3。")


def build_authorized_request(
    payload: OnlineRequestPayload,
    data_level: DataLevel,
    *,
    user_approved: bool,
    exception_approved: bool = False,
) -> AuthorizedOnlineRequest:
    decision = evaluate_online_boundary(
        data_level,
        exception_approved=exception_approved,
    )
    if not decision.allowed:
        raise AuthorizationError(decision.reason)
    if decision.requires_per_request_approval and not user_approved:
        raise AuthorizationError("该数据等级必须获得本次请求的明确授权。")
    return AuthorizedOnlineRequest(
        payload=payload,
        payload_json=payload.canonical_json(),
        fingerprint=payload.fingerprint(),
        data_level=data_level,
        decision=decision,
    )


def verify_authorized_payload(
    authorized: AuthorizedOnlineRequest,
    actual_payload: OnlineRequestPayload,
) -> bool:
    return (
        actual_payload.canonical_json() == authorized.payload_json
        and actual_payload.fingerprint() == authorized.fingerprint
    )
