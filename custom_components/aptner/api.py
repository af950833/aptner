from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientResponseError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)

class AptnerError(Exception):
    """Base exception for Aptner."""

class AptnerAuthError(AptnerError):
    """Raised when authentication fails."""

class AptnerClient:
    def __init__(self, hass, user_id: str, password: str) -> None:
        self._hass = hass
        self._id = user_id
        self._password = password
        self._token: str | None = None
        self._auth_lock = asyncio.Lock()

    @property
    def _session(self):
        return async_get_clientsession(self._hass)

    async def authenticate(self) -> None:
        """Obtain a new access token."""
        async with self._auth_lock:
            payload = {"id": self._id, "password": self._password}
            data = await self._raw_request("POST", "/auth/token", json=payload, auth=False)
            token = None
            if isinstance(data, dict):
                token = data.get("accessToken")
            if not token:
                raise AptnerAuthError("Failed to obtain accessToken")
            self._token = token

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        auth: bool = True,
    ) -> Any:
        headers = {"Content-Type": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        url = f"{BASE_URL}{path}"
        async with self._session.request(method, url, headers=headers, json=json) as resp:
            if resp.status >= 400:
                # Keep body for debugging
                body = await resp.text()
                raise ClientResponseError(
                    resp.request_info,
                    resp.history,
                    status=resp.status,
                    message=body,
                    headers=resp.headers,
                )
            try:
                return await resp.json()
            except Exception:
                return None

    async def request(self, method: str, path: str, *, json: dict | None = None) -> Any:
        """Request with auto re-auth on 401 and retry on other errors."""
        max_retries = 3
        base_delay = 1  # 초
        
        for attempt in range(max_retries):
            try:
                return await self._raw_request(method, path, json=json, auth=True)
            except ClientResponseError as e:
                # 401 에러: 인증 갱신 시도
                if e.status == 401 and path != "/auth/token":
                    if attempt == 0:  # 첫 번째 시도에서만 인증 갱신
                        try:
                            await self.authenticate()
                        except Exception as auth_error:
                            _LOGGER.warning("Authentication failed during retry: %s", auth_error)
                    else:
                        _LOGGER.warning("401 error persists after re-authentication")
                    continue
                # 다른 HTTP 에러나 네트워크 오류
                elif attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    _LOGGER.warning(
                        "Request failed (attempt %d/%d): %s. Retrying in %.1f seconds...",
                        attempt + 1, max_retries, str(e), delay
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    _LOGGER.error("Request failed after %d attempts: %s", max_retries, str(e))
                    raise
            except Exception as e:  # 네트워크 에러, 타임아웃 등
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    _LOGGER.warning(
                        "Request failed (attempt %d/%d): %s. Retrying in %.1f seconds...",
                        attempt + 1, max_retries, str(e), delay
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    _LOGGER.error("Request failed after %d attempts: %s", max_retries, str(e))
                    raise
        
        # 마지막 재시도 후 인증 갱신 시도 (401이 아니더라도)
        if path != "/auth/token":
            try:
                await self.authenticate()
            except Exception as auth_error:
                _LOGGER.warning("Final authentication attempt failed: %s", auth_error)
        
        # 마지막 시도
        return await self._raw_request(method, path, json=json, auth=True)

    # ---- High-level API (mirrors pyscript services) ----

    async def get_fee(self) -> dict:
        data = await self.request("GET", "/fee/detail")
        fee = data["fee"]
        return {
            "year": fee.get("year"),
            "month": fee.get("month"),
            "fee": fee.get("currentFee"),
            "details": {item["name"]: item["value"] for item in fee.get("details", [])},
        }

    async def find_car(self, carno: str | None = None) -> dict:
        """Find car entry/exit records (기존 기능 유지)."""
        monthly_access = await self.request("GET", "/pc/monthly-access-history")
        response: dict[str, dict[str, Any]] = {}
        for monthly_parking in monthly_access.get("monthlyParkingHistoryList", []):
            for report in monthly_parking.get("visitCarUseHistoryReportList", []):
                if carno is None or report.get("carNo") == carno:
                    cno = report.get("carNo")
                    if not cno:
                        continue
                    if cno not in response:
                        response[cno] = {
                            "status": "out" if report.get("isExit") else "in",
                        }
                        if report.get("inDatetime") is not None:
                            response[cno]["intime"] = report.get("inDatetime")
                        if report.get("outDatetime") is not None:
                            response[cno]["outtime"] = report.get("outDatetime")
                    if report.get("carNo") == carno:
                        break
        return response

    async def get_car_status(self, carno: str | None = None) -> dict:
        """Get current car status for device_tracker (새로운 메서드)."""
        monthly_access = await self.request("GET", "/pc/monthly-access-history")
        response = {}
        
        # 모든 차량의 가장 최근 기록 찾기
        latest_records = {}
        
        for monthly_parking in monthly_access.get("monthlyParkingHistoryList", []):
            for report in monthly_parking.get("visitCarUseHistoryReportList", []):
                cno = report.get("carNo")
                if not cno:
                    continue
                    
                # 특정 차량만 요청한 경우 필터링
                if carno is not None and cno != carno:
                    continue
                    
                # 가장 최근 기록만 저장 (datetime 비교)
                report_time = report.get("inDatetime") or report.get("outDatetime")
                if report_time:
                    if cno not in latest_records:
                        latest_records[cno] = report
                    else:
                        # 이미 있는 기록보다 최신인지 확인
                        existing_time = latest_records[cno].get("inDatetime") or latest_records[cno].get("outDatetime")
                        if report_time > existing_time:
                            latest_records[cno] = report
        
        # 결과 구성
        for cno, report in latest_records.items():
            response[cno] = {
                "carNo": cno,
                "isExit": report.get("isExit", True),
                "inDatetime": report.get("inDatetime"),
                "outDatetime": report.get("outDatetime"),
                "status": "out" if report.get("isExit") else "in"
            }
        
        # 특정 차량 요청했는데 데이터가 없는 경우
        if carno is not None and carno not in response:
            response[carno] = {
                "carNo": carno,
                "isExit": True,  # 기본값 not_home
                "inDatetime": None,
                "outDatetime": None,
                "intime": None,
                "outtime": None,
                "status": "not_found"
            }
        
        return response

    async def get_reserve_status(self) -> dict:
        # Matches pyscript: fetch all pages and compress into ranges per car
        from datetime import datetime, timedelta, date

        total_pages = 0
        current_page = 0
        today = date.today()
        result: dict[str, list[date]] = {}

        while True:
            current_page += 1
            reserved = await self.request("GET", f"/pc/reserves?pg={current_page}")
            if total_pages == 0:
                total_pages = int(reserved.get("totalPages", 0) or 0)
            for item in reserved.get("reserveList", []):
                visit_date_str = item.get("visitDate")
                try:
                    visit_date = datetime.strptime(visit_date_str, "%Y.%m.%d").date()
                except Exception:
                    continue
                if today <= visit_date:
                    car_no = item.get("carNo")
                    if not car_no:
                        continue
                    result.setdefault(car_no, []).append(visit_date)

            if total_pages and current_page >= total_pages:
                break
            if not total_pages and current_page >= 20:
                # Safety break if API doesn't return totalPages
                break

        # Compress to ranges
        out: dict[str, list[dict[str, str]]] = {}
        for car, dates in result.items():
            dates.sort()
            ranges: list[dict[str, str]] = []
            start = dates[0]
            for i in range(1, len(dates)):
                prev = dates[i - 1]
                cur = dates[i]
                if (cur - prev) > timedelta(days=1):
                    ranges.append({"from": start.isoformat(), "to": prev.isoformat()})
                    start = cur
            ranges.append({"from": start.isoformat(), "to": dates[-1].isoformat()})
            out[car] = ranges
        return out

    async def reserve_car(self, *, date: str, purpose: str, carno: str, days: int, phone: str) -> None:
        payload = {
            "visitDate": date,
            "purpose": purpose,
            "carNo": carno,
            "days": days,
            "phone": phone,
        }
        await self.request("POST", "/pc/reserve/", json=payload)
