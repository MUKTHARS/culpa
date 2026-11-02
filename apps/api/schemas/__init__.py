"""Pydantic request bodies. Responses are plain dicts built by services."""

from pydantic import BaseModel, Field


class ShopRequest(BaseModel):
    buyer_id: str = Field(min_length=1, max_length=80)
    instruction: str = Field(min_length=3, max_length=500)
    max_amount: str | None = Field(default=None, max_length=12)
    category: str | None = Field(default=None, max_length=120)
    required_attributes: dict[str, str] = Field(default_factory=dict)
    device_id: str | None = Field(default=None, max_length=120)


class CaptureRequest(BaseModel):
    token: str = Field(min_length=3, max_length=64)


class ProductUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    price: str | None = Field(default=None, pattern=r"^\d{1,7}(\.\d{1,2})?$")
    attributes: dict[str, str] | None = None


class SimulateDispute(BaseModel):
    order_id: str
    reason: str = "ITEM_NOT_AS_DESCRIBED"
    claim_text: str = Field(default="", max_length=4000)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ApproveRequest(BaseModel):
    action: str | None = Field(default=None, pattern=r"^(refund_full|refund_partial|contest)$")
    # Only for refund_partial: an analyst-chosen amount instead of the policy's.
    amount: str | None = Field(default=None, pattern=r"^\d{1,7}(\.\d{1,2})?$")
    note: str | None = Field(default=None, max_length=1000)
