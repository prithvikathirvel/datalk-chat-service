from pydantic import BaseModel, field_validator
from typing import List, Optional
import re

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    @field_validator('message')
    @classmethod
    def validate(cls, value):
        if re.search(r"<script.*?>.*?</script>", value, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")
        if "\0" in value:
            raise ValueError("Content contains null bytes")
        return value
    

    
