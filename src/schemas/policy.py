from pydantic import BaseModel

class PolicySearchRequest(BaseModel):
    query : str