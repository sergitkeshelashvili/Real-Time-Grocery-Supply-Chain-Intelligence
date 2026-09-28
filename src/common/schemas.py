from datetime import datetime, timezone
from typing import Any
import math
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator

class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "simulator"
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_contract(self):
        allowed = {"orders", "inventory", "deliveries", "prices", "demand_signals", "weather_observation", "waste"}
        if self.event_type not in allowed:
            raise ValueError("unsupported event_type")
        if self.event_type != "weather_observation":
            if not self.payload.get("store_id") or not self.payload.get("product_id"):
                raise ValueError("store_id and product_id are required")
        numeric = ("quantity", "requested_quantity", "lost_sales_quantity", "unit_price", "ordered_quantity", "delivered_quantity", "reorder_point", "safety_stock", "recommended_order_quantity", "unit_cost")
        for key in numeric:
            if key in self.payload:
                value = self.payload[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"{key} must be a finite non-negative number")
        return self
