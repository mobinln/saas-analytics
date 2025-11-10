from pydantic import BaseModel
from enum import Enum


class EventType(str, Enum):
    PAGE_VIEW = "page_view"
    BUTTON_CLICK = "button_click"
    API_CALL = "api_call"
    FEATURE_USAGE = "feature_usage"
    FORM_SUBMIT = "form_submit"


class EventRequest(BaseModel):
    event_type: EventType
    user_id: str
    session_id: str
    event_data: dict
