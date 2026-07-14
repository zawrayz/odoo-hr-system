from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from odoo import fields, http
from odoo.http import request


class HrBiometricBridgeController(http.Controller):

    @staticmethod
    def _normalize_event(value):
        value = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

        if value in {"checkin", "check_in", "in", "entry", "0"}:
            return "check_in"

        if value in {"checkout", "check_out", "out", "exit", "1"}:
            return "check_out"

        return "unknown"

    @staticmethod
    def _parse_punch_time(value):
        if not value:
            return False

        text = str(value).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        parsed = None

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            formats = (
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
                "%m/%d/%Y %H:%M:%S",
            )

            for date_format in formats:
                try:
                    parsed = datetime.strptime(text, date_format)
                    break
                except ValueError:
                    continue

        if parsed is None:
            return False

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Karachi"))

        parsed_utc = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return fields.Datetime.to_string(parsed_utc)

    @http.route(
        "/biometric/punch",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def biometric_punch(self, **kwargs):
        config = request.env["ir.config_parameter"].sudo()
        expected_token = config.get_param("hr_biometric_bridge.token") or ""
        supplied_token = request.httprequest.headers.get("X-Biometric-Token", "")

        if not expected_token:
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "Bridge token is not configured.",
                },
                status=503,
            )

        if not supplied_token or not hmac.compare_digest(
            supplied_token,
            expected_token,
        ):
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "Unauthorized.",
                },
                status=401,
            )

        raw_body = request.httprequest.get_data(cache=True) or b""
        content_type = request.httprequest.headers.get("Content-Type", "").lower()

        try:
            if "application/json" in content_type:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            else:
                payload = dict(request.get_http_params())
        except (ValueError, TypeError, json.JSONDecodeError):
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "Invalid request payload.",
                },
                status=400,
            )

        device_code = str(
            payload.get("device")
            or payload.get("device_code")
            or payload.get("cn")
            or "UNKNOWN"
        ).strip()

        employee_code = str(
            payload.get("employee_code")
            or payload.get("employee_id")
            or payload.get("user_id")
            or ""
        ).strip()

        event_type = self._normalize_event(
            payload.get("event")
            or payload.get("event_type")
            or payload.get("punch_type")
        )

        timestamp_value = (
            payload.get("timestamp")
            or payload.get("time")
            or payload.get("punch_time")
        )

        punch_time = self._parse_punch_time(timestamp_value)

        if not employee_code:
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "Employee code is required.",
                },
                status=400,
            )

        if not punch_time:
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "A valid punch timestamp is required.",
                },
                status=400,
            )

        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        request_hash = hashlib.sha256(canonical_payload).hexdigest()

        Punch = request.env["hr.biometric.punch"].sudo()
        existing = Punch.search(
            [("request_hash", "=", request_hash)],
            limit=1,
        )

        if existing:
            return request.make_json_response(
                {
                    "ok": True,
                    "duplicate": True,
                    "punch_id": existing.id,
                },
                status=200,
            )

        Employee = request.env["hr.employee"].sudo().with_context(
            active_test=False
        )
        employee = Employee.search(
            [("employee_code", "=", employee_code)],
            limit=1,
        )

        forwarded_for = request.httprequest.headers.get("X-Forwarded-For", "")
        source_ip = (
            request.httprequest.headers.get("CF-Connecting-IP")
            or forwarded_for.split(",")[0].strip()
            or request.httprequest.remote_addr
        )

        punch = Punch.create(
            {
                "device_code": device_code,
                "employee_code": employee_code,
                "employee_id": employee.id if employee else False,
                "event_type": event_type,
                "punch_time": punch_time,
                "source_ip": source_ip,
                "request_hash": request_hash,
                "raw_payload": raw_body.decode("utf-8", errors="replace")
                or json.dumps(payload, ensure_ascii=False, default=str),
                "state": "mapped" if employee else "received",
            }
        )

        return request.make_json_response(
            {
                "ok": True,
                "duplicate": False,
                "punch_id": punch.id,
                "employee_mapped": bool(employee),
                "employee_name": employee.name if employee else False,
            },
            status=201,
        )
