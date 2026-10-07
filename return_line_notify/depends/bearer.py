from typing import Optional

from fastapi import Header, HTTPException


def bearer_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=400, detail="Invalid or missing Authorization header"
        )

    return authorization[len("Bearer ") :]
