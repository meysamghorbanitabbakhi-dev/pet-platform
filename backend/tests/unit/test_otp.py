from uuid import uuid4

from app.modules.identity.models import OtpChallenge
from app.modules.identity.otp import generate_otp_code, hash_otp_code, otp_matches


def test_generated_otp_is_six_numeric_digits() -> None:
    code = generate_otp_code()

    assert len(code) == 6
    assert code.isdigit()


def test_otp_hash_is_bound_to_challenge_and_mobile() -> None:
    challenge_id = uuid4()
    mobile = "+989121234567"
    code = "483920"
    challenge = OtpChallenge(
        id=challenge_id,
        mobile_e164=mobile,
        code_hash=hash_otp_code(
            pepper="a-secure-test-pepper-that-is-long-enough",
            challenge_id=challenge_id,
            mobile_e164=mobile,
            code=code,
        ),
        delivery_status="sent",
        attempts=0,
        max_attempts=5,
    )

    assert otp_matches(
        pepper="a-secure-test-pepper-that-is-long-enough",
        challenge=challenge,
        candidate_code=code,
    )
    assert not otp_matches(
        pepper="a-secure-test-pepper-that-is-long-enough",
        challenge=challenge,
        candidate_code="000000",
    )
