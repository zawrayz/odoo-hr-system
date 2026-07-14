from __future__ import annotations

import hmac
import json

from odoo import fields, http
from odoo.http import request


class HrBiometricHeartbeatController(http.Controller):

    @staticmethod
    def _source_ip():
        forwarded_for = request.httprequest.headers.get(
            "X-Forwarded-For",
            "",
        )

        return (
            request.httprequest.headers.get(
                "CF-Connecting-IP"
            )
            or forwarded_for.split(",")[0].strip()
            or request.httprequest.remote_addr
        )

    @http.route(
        "/biometric/heartbeat",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def biometric_heartbeat(self, **kwargs):
        config = request.env[
            "ir.config_parameter"
        ].sudo()

        expected_token = (
            config.get_param(
                "hr_biometric_bridge.token"
            )
            or ""
        )

        supplied_token = (
            request.httprequest.headers.get(
                "X-Biometric-Token",
                "",
            )
        )

        if (
            not expected_token
            or not supplied_token
            or not hmac.compare_digest(
                supplied_token,
                expected_token,
            )
        ):
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "Unauthorized.",
                },
                status=401,
            )

        raw_body = (
            request.httprequest.get_data(
                cache=True
            )
            or b""
        )

        content_type = (
            request.httprequest.headers.get(
                "Content-Type",
                "",
            ).lower()
        )

        try:
            if "application/json" in content_type:
                payload = (
                    json.loads(
                        raw_body.decode("utf-8")
                    )
                    if raw_body
                    else {}
                )
            else:
                payload = dict(
                    request.get_http_params()
                )
        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "Invalid request payload.",
                },
                status=400,
            )

        bridge_id = str(
            payload.get("bridge_id") or ""
        ).strip()

        bridge_name = str(
            payload.get("bridge_name")
            or bridge_id
            or ""
        ).strip()

        if not bridge_id:
            return request.make_json_response(
                {
                    "ok": False,
                    "error": "Bridge ID is required.",
                },
                status=400,
            )

        Status = request.env[
            "hr.biometric.bridge.status"
        ].sudo()

        status_record = Status.search(
            [
                ("bridge_id", "=", bridge_id),
            ],
            limit=1,
        )

        values = {
            "bridge_id": bridge_id,
            "bridge_name": bridge_name,
            "device_code": str(
                payload.get("device")
                or payload.get("device_code")
                or ""
            ).strip(),
            "last_seen": fields.Datetime.now(),
            "source_ip": self._source_ip(),
            "app_version": str(
                payload.get("app_version")
                or ""
            ).strip(),
            "machine_name": str(
                payload.get("machine_name")
                or ""
            ).strip(),
            "last_message": str(
                payload.get("message")
                or "Heartbeat received"
            ).strip(),
            "active": True,
        }

        if status_record:
            status_record.write(values)
            created = False
        else:
            status_record = Status.create(values)
            created = True

        return request.make_json_response(
            {
                "ok": True,
                "created": created,
                "bridge_record_id": status_record.id,
                "bridge_id": status_record.bridge_id,
                "server_time": fields.Datetime.to_string(
                    fields.Datetime.now()
                ),
            },
            status=201 if created else 200,
        )
