from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from research_desk.security import AuthorizedOnlineRequest


class ProviderKind(str, Enum):
    LOCAL = "local"
    ONLINE = "online"


class ProviderStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"
    VERIFIED = "verified"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class ProviderInfo:
    kind: ProviderKind
    name: str
    status: ProviderStatus
    detail: str


class ProviderUnavailable(RuntimeError):
    pass


class AIProvider(Protocol):
    @property
    def info(self) -> ProviderInfo: ...

    def send(self, request: AuthorizedOnlineRequest) -> str: ...


@dataclass(frozen=True)
class UnavailableProvider:
    info: ProviderInfo

    def send(self, request: AuthorizedOnlineRequest) -> str:
        raise ProviderUnavailable(f"{self.info.name}不可用：{self.info.detail}")


class ProviderRegistry:
    def providers(self) -> list[AIProvider]:
        return [
            UnavailableProvider(
                ProviderInfo(
                    kind=ProviderKind.LOCAL,
                    name="本地模型",
                    status=ProviderStatus.NOT_CONFIGURED,
                    detail="尚未配置本地模型运行时；基础统计不受影响。",
                )
            ),
            UnavailableProvider(
                ProviderInfo(
                    kind=ProviderKind.ONLINE,
                    name="在线模型",
                    status=ProviderStatus.NOT_CONFIGURED,
                    detail="在线 Provider 未配置，不会创建或发送网络请求。",
                )
            ),
        ]

    def list_providers(self) -> list[ProviderInfo]:
        return [provider.info for provider in self.providers()]


class GuidanceService:
    def suggest_next_steps(self, numeric_fields: int, categorical_fields: int, inference_allowed: bool) -> list[str]:
        suggestions = []
        if numeric_fields >= 2:
            suggestions.append("可先检查字段分布，再选择 Pearson 或 Spearman 并查看基础散点诊断。")
        if numeric_fields >= 2:
            suggestions.append("如这些字段属于同一量表，可检查题项方向后进行信度分析。")
        if categorical_fields:
            suggestions.append("分类字段优先查看频数和缺失情况，再决定是否纳入进一步分析。")
        if not inference_allowed:
            suggestions.append("当前抽样声明不允许正式总体推断，结果只能作为未加权描述。")
        if not suggestions:
            suggestions.append("先确认字段类型和缺失规则，再开始选择分析。")
        return suggestions
