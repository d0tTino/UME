from __future__ import annotations

from uuid import uuid4
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from .config import settings
from .api_deps import TOKENS

router = APIRouter(prefix="/auth")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token")
def issue_token(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    if (
        form_data.username == settings.UME_OAUTH_USERNAME
        and form_data.password == settings.UME_OAUTH_PASSWORD
    ):
        token = str(uuid4())
        expires_at = time.time() + settings.UME_OAUTH_TTL
        TOKENS[token] = (settings.UME_OAUTH_ROLE, expires_at)
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=400, detail="Invalid credentials")
