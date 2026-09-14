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
    approval_tools = {
        "file.write",
        "sandbox.execute",
        "document.create",
        "presentation.create",
        "pdf.create",
        "spreadsheet.create",
    }

    def evaluate(self, tool_name: str) -> PolicyDecision:
        return PolicyDecision.REQUIRE_APPROVAL if tool_name in self.approval_tools else PolicyDecision.ALLOW
