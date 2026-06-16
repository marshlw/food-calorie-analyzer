"""API client module for ai-healthy service.

Provides a reusable async HTTP client with token refresh, retry,
connection pooling, and JSON-only response handling.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


TokenLoader = Callable[[int], Tuple[Optional[str], Optional[str]]]
TokenSaver = Callable[[int, str, str], None]
TokenClearer = Callable[[int], None]


class APIClient:
    def __init__(
        self,
        base_url: str,
        token_loader: TokenLoader,
        token_saver: TokenSaver,
        token_clearer: TokenClearer,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.token_loader = token_loader
        self.token_saver = token_saver
        self.token_clearer = token_clearer
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=5.0, read=timeout, write=timeout),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def register(self, user_id: int, email: str, password: str) -> Tuple[bool, Optional[str]]:
        try:
            response = await self.client.post(
                "/api/v1/register",
                json={"email": email, "password": password},
            )
            response.raise_for_status()
            return True, None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                return False, "User already exists"
            return False, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning("Register request failed", exc_info=exc)
            return False, "Request timeout"
        except Exception as exc:
            logger.exception("Register error")
            return False, str(exc)

    async def login(self, user_id: int, email: str, password: str) -> Tuple[bool, Optional[str]]:
        try:
            response = await self.client.post(
                "/api/v1/login",
                json={"email": email, "password": password, "grant_type": "password"},
            )
            response.raise_for_status()
            data = response.json()
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            if not access_token:
                return False, "No access token returned"
            self.token_saver(user_id, access_token, refresh_token or "")
            return True, None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return False, "Invalid email or password"
            return False, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning("Login request failed", exc_info=exc)
            return False, "Request timeout"
        except Exception as exc:
            logger.exception("Login error")
            return False, str(exc)

    async def refresh_access_token(self, user_id: int) -> Tuple[bool, Optional[str]]:
        access_token, refresh_token = self.token_loader(user_id)
        if not refresh_token:
            self.token_clearer(user_id)
            return False, "No refresh token"

        try:
            response = await self.client.post(
                "/api/v1/token",
                json={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )
            response.raise_for_status()
            data = response.json()
            new_access = data.get("access_token")
            new_refresh = data.get("refresh_token")
            if not new_access:
                return False, "No access token returned"
            self.token_saver(user_id, new_access, new_refresh or refresh_token)
            return True, None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.token_clearer(user_id)
                return False, "Refresh token expired"
            return False, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning("Refresh token request failed", exc_info=exc)
            return False, "Request timeout"
        except Exception as exc:
            logger.exception("Refresh token error")
            return False, str(exc)

    async def _request(
        self, user_id: int, method: str, endpoint: str, **kwargs: Any
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        access_token, _ = self.token_loader(user_id)
        if access_token:
            headers = kwargs.pop("headers", {})
            headers["Authorization"] = f"Bearer {access_token}"
            kwargs["headers"] = headers
        kwargs.setdefault("timeout", self.timeout)

        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(method, endpoint, **kwargs)
                if response.status_code == 401 and attempt == 0:
                    refreshed, err = await self.refresh_access_token(user_id)
                    if refreshed:
                        access_token, _ = self.token_loader(user_id)
                        headers = kwargs.get("headers", {})
                        headers["Authorization"] = f"Bearer {access_token}"
                        kwargs["headers"] = headers
                        continue
                    return None, err
                response.raise_for_status()
                try:
                    return response.json(), None
                except ValueError:
                    return {}, None
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if 500 <= status < 600 and attempt + 1 < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 10))
                    continue
                try:
                    error_data = exc.response.json()
                    return None, error_data.get("detail", f"HTTP {status}")
                except Exception:
                    return None, f"HTTP {status}"
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning("HTTP request failed", exc_info=exc)
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 10))
                    continue
                return None, "Request timeout"
            except Exception as exc:
                logger.exception("Unexpected request error")
                return None, str(exc)

        return None, "Request failed after retries"

    async def upload_photo(self, user_id: int, file_bytes: bytes, filename: str = "image.jpg") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        files = {"file": (filename, file_bytes, "image/jpeg")}
        return await self._request(user_id, "POST", "/api/v1/analyze", files=files)

    async def get_task_status(self, user_id: int, task_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return await self._request(user_id, "GET", f"/api/v1/task/{task_id}")

    async def submit_feedback(self, user_id: int, task_id: str, correct_food: str, correct_weight: int) -> Tuple[bool, Optional[str]]:
        result, error = await self._request(
            user_id,
            "POST",
            "/api/v1/feedback",
            json={
                "task_id": task_id,
                "correct_food": correct_food,
                "correct_weight": correct_weight,
            },
        )
        return result is not None, error

    async def get_current_user(self, user_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return await self._request(user_id, "GET", "/api/v1/me")


_client: Optional[APIClient] = None


def get_client(
    base_url: str,
    token_loader: TokenLoader,
    token_saver: TokenSaver,
    token_clearer: TokenClearer,
) -> APIClient:
    global _client
    if _client is None:
        _client = APIClient(base_url, token_loader, token_saver, token_clearer)
    return _client
