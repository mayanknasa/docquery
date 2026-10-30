import secrets

from fastapi import Header, HTTPException, Request


async def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.api_key
    if expected and not secrets.compare_digest(x_api_key or "", expected):  # constant time compare
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
