import json
import os

import firebase_admin
from firebase_admin import auth, credentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXCLUDED_PATHS = {
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
}


def setup_firebase_auth():
    if firebase_admin._apps:
        return

    credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if not credentials_json:
        raise RuntimeError("FIREBASE_CREDENTIALS_JSON is required.")

    try:
        credential_dict = json.loads(credentials_json)
    except json.JSONDecodeError as e:
        raise RuntimeError("FIREBASE_CREDENTIALS_JSON is not valid JSON.") from e

    firebase_admin.initialize_app(credentials.Certificate(credential_dict))


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header."},
            )

        token = auth_header[len("Bearer ") :].strip()
        if not token:
            return JSONResponse(
                status_code=401, content={"detail": "Empty Bearer token."}
            )

        try:
            decoded_token = auth.verify_id_token(token)
            request.state.firebase_user = decoded_token
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired Firebase token."},
            )

        return await call_next(request)
