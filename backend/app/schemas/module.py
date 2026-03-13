from pydantic import BaseModel


class ModuleResponse(BaseModel):
    module: str
    enabled: bool
    label: str
    description: str
    locked: bool

    model_config = {"from_attributes": True}


class ModuleUpdate(BaseModel):
    enabled: bool
