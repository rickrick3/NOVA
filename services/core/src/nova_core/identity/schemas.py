from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64)]
    password: Annotated[str, StringConstraints(min_length=10, max_length=128)]


class UserOut(BaseModel):
    id: str
    username: str


class SetupOut(BaseModel):
    user: UserOut


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime
