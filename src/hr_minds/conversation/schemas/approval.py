from pydantic import BaseModel, ConfigDict


class ApprovalDecision(BaseModel):
    """
    Request body for POST /conversations/{id}/approvals.
    Client specifies whether to approve or reject the pending tool execution.
    """

    model_config = ConfigDict(extra="forbid")

    approve: bool


ApprovalRequest = ApprovalDecision
