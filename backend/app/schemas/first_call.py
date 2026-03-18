from pydantic import BaseModel


class FirstCallExtractionRequest(BaseModel):
    text: str
    existing_values: dict | None = None


class ExtractedFieldValue(BaseModel):
    value: str | int | bool | None
    confidence: float
    is_new: bool


class FirstCallExtractionResponse(BaseModel):
    extracted: dict[str, ExtractedFieldValue]
    not_extracted: list[str]
    fields_updated: int
