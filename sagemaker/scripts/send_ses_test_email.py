"""
One-off SES test using SendRawEmail (same API as the daily-report Lambda).

Run from the sagemaker/ folder with dev deps installed (boto3 via requirements-aws.txt):

  cd sagemaker
  # Set in .env: REPORT_EMAIL_FROM, REPORT_EMAIL_TO, AWS_REGION, credentials
  python scripts/send_ses_test_email.py

Or one-liner (PowerShell):

  $env:REPORT_EMAIL_FROM='verified-sender@yourdomain.com'
  $env:REPORT_EMAIL_TO='recipient@yourdomain.com'
  python scripts/send_ses_test_email.py

Sandbox: verify BOTH From and To identities in SES (same region). Production: verify From only.
"""

from __future__ import annotations

import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

_CONFIG = Path(__file__).resolve().parent.parent / "config"
sys.path.insert(0, str(_CONFIG))

import boto3  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402

from aws_config import AWS_REGION  # noqa: E402


def main() -> None:
    src = os.environ.get("REPORT_EMAIL_FROM", "").strip()
    dst = os.environ.get("REPORT_EMAIL_TO", "").strip()
    if not src or not dst:
        sys.exit(
            "Set REPORT_EMAIL_FROM and REPORT_EMAIL_TO (e.g. in sagemaker/.env).\n"
            "In SES sandbox, verify both addresses (or the domain) in this region."
        )

    html = """\
<!DOCTYPE html><html><body>
<p>This is a <b>SES test</b> from the bike-sharing project (<code>send_ses_test_email.py</code>).</p>
<p>If you see this, the sender identity and (if sandbox) recipient are verified, and IAM allows sending.</p>
</body></html>"""

    msg = MIMEMultipart("mixed")
    msg["Subject"] = "SES test — bike demand report pipeline"
    msg["From"] = src
    msg["To"] = dst
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    client = boto3.client("ses", region_name=AWS_REGION)
    try:
        out = client.send_raw_email(
            Source=src,
            Destinations=[dst],
            RawMessage={"Data": msg.as_string().encode("utf-8")},
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg_txt = e.response.get("Error", {}).get("Message", str(e))
        print(f"SES rejected the send: {code}: {msg_txt}", file=sys.stderr, flush=True)
        print(
            "Common fixes: verify From (and To in sandbox) in this region; "
            "IAM needs ses:SendRawEmail; From must match a verified identity.",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from e

    mid = out.get("MessageId", "")
    print(
        f"SES accepted the message (delivery is separate). MessageId={mid!r}",
        flush=True,
    )
    print(f"From {src!r} -> To {dst!r}  |  region={AWS_REGION}", flush=True)
    print(
        "If the message does not arrive within ~5 minutes: check Spam/Promotions, "
        "corporate quarantine, and run: python scripts/ses_diagnose.py",
        flush=True,
    )


if __name__ == "__main__":
    main()
