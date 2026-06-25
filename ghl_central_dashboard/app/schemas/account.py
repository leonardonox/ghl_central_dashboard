from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location_id: str = Field(min_length=3, max_length=150)
    api_token: str = Field(min_length=10)


class AccountUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location_id: str = Field(min_length=3, max_length=150)
    api_token: str | None = Field(default=None, min_length=10)
    active: bool = True


class AccountOut(BaseModel):
    id: int
    name: str
    location_id: str
    active: bool

    model_config = {'from_attributes': True}
