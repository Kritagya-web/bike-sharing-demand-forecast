"""
Print SES region, send quota (sandbox hint), and verification status for REPORT_EMAIL_FROM / REPORT_EMAIL_TO.

Uses the same .env as other scripts (sagemaker/.env via config/aws_config.py).

  cd sagemaker
  python scripts/ses_diagnose.py

If API send "succeeds" but mail never appears: check spam/junk, suppression list, and
receiving-server quarantine. Use MessageId from send_ses_test_email.py in support cases.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_CONFIG = Path(__file__).resolve().parent.parent / "config"
sys.path.insert(0, str(_CONFIG))

import boto3  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402

from aws_config import AWS_REGION  # noqa: E402


def main() -> None:
    src = os.environ.get("REPORT_EMAIL_FROM", "").strip()
    dst = os.environ.get("REPORT_EMAIL_TO", "").strip()

    print(f"AWS_REGION (from env / default): {AWS_REGION}", flush=True)
    client = boto3.client("ses", region_name=AWS_REGION)

    try:
        q = client.get_send_quota()
        mx = q.get("Max24HourSend")
        sent = q.get("SentLast24Hours")
        print(f"Max24HourSend: {mx}  |  SentLast24Hours: {sent}", flush=True)
        if mx is not None and float(mx) <= 200:
            print(
                "  -> Low daily cap often means SES is still in SANDBOX: "
                "only verified identities can receive; consider production access.",
                flush=True,
            )
    except ClientError as e:
        print(f"get_send_quota failed: {e}", flush=True)

    try:
        ae = client.get_account_sending_enabled()
        print(f"AccountSendingEnabled: {ae.get('Enabled')}", flush=True)
    except ClientError as e:
        print(f"get_account_sending_enabled: {e}", flush=True)

    identities = [x for x in (src, dst) if x]
    if not identities:
        print("Set REPORT_EMAIL_FROM and REPORT_EMAIL_TO to check verification status.", flush=True)
        return

    try:
        resp = client.get_identity_verification_attributes(Identities=identities)
        attrs = resp.get("VerificationAttributes", {})
        for ident in identities:
            a = attrs.get(ident, {})
            status = a.get("VerificationStatus", "NOT_FOUND_IN_SES")
            print(f"Identity {ident!r}: {status}", flush=True)
            if status != "Success":
                print(
                    "  -> In THIS region, create/verify this identity (SES > Verified identities).",
                    flush=True,
                )
    except ClientError as e:
        print(f"get_identity_verification_attributes failed: {e}", flush=True)

    print(
        "\nIf SendRawEmail returned MessageId but inbox is empty:\n"
        "  - Spam / Promotions / quarantine (especially corporate domains).\n"
        "  - Wait a few minutes; check SES > Configuration sets / suppression (if used).\n"
        "  - Receiving MX may delay or drop mail from new amazonses.com reputations.\n",
        flush=True,
    )


if __name__ == "__main__":
    main()
