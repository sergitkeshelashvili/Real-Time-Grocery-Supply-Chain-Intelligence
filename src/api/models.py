from pydantic import BaseModel
from datetime import datetime

class Health(BaseModel): status: str
class Overview(BaseModel): events_processed: int; orders: int; inventory_observations: int; low_stock_observations: int; active_alerts: int; stockout_rate: float

class PromptRequest(BaseModel):
    prompt: str

class PromptResponse(BaseModel):
    prompt: str
    answer: str
    generated_at: datetime
    provider: str
    data_context: dict
