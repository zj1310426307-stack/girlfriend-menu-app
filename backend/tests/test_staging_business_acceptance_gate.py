"""Safety contracts for the authenticated hosted-staging acceptance gate."""

from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "check_staging_business_flows.py"
SPEC = spec_from_file_location("check_staging_business_flows", SCRIPT_PATH)
assert SPEC and SPEC.loader
gate = module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def test_credentials_are_bounded_distinct_and_redacted():
    sentinels = {
        "admin_password": "password-private-sentinel",
        "admin_invite_code": "admin-private-sentinel",
        "customer_invite_code": "customer-private-sentinel",
    }
    credentials = gate._credentials_from_payload(sentinels)

    assert all(value not in repr(credentials) for value in sentinels.values())
    with pytest.raises(gate.StagingAcceptanceError):
        gate._credentials_from_payload({})
    with pytest.raises(gate.StagingAcceptanceError):
        gate._credentials_from_payload(
            {
                "admin_password": "password",
                "admin_invite_code": "same-invite",
                "customer_invite_code": "same-invite",
            }
        )


def test_upload_fixture_is_a_valid_png():
    image = Image.open(BytesIO(gate.PNG_FIXTURE))
    image.verify()
    assert image.format == "PNG"


def test_http_failure_does_not_echo_response_body_or_url():
    response = gate.httpx.Response(
        401,
        request=gate.httpx.Request("POST", "https://staging.example/api/admin/login"),
        json={"detail": "password-private-sentinel"},
    )

    with pytest.raises(gate.StagingAcceptanceError) as raised:
        gate._expect_status(response, 200, "admin login")

    message = str(raised.value)
    assert "password-private-sentinel" not in message
    assert "staging.example" not in message
    assert message == "admin login returned unexpected HTTP 401"
