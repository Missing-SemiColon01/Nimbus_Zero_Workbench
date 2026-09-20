try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class PolicyEngine:
    def __init__(self, approval_tools: set[str] | None = None):
        self.approval_tools = approval_tools or set()

    def evaluate(self, tool_name: str) -> PolicyDecision:
        if tool_name in self.approval_tools:
            return PolicyDecision.REQUIRE_APPROVAL
        return PolicyDecision.ALLOW  # Default autonomous ALLOW
