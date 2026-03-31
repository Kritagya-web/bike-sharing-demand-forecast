# AWS: SageMaker endpoint + daily email report

This guide matches the `lambda/daily_report` function and [`config/deploy_endpoint.py`](../config/deploy_endpoint.py).

## 1. Train and get `model.tar.gz` on S3

Upload `data/raw/hour.csv` to S3 (see `scripts/upload_data.sh`), set `SAGEMAKER_ROLE_ARN`, `SAGEMAKER_BUCKET`, then:

```bash
cd sagemaker
python pipeline.py train-sagemaker
```

Copy the printed `MODEL_DATA_S3=...` value (ends with `model.tar.gz`).

## 2. Deploy the real-time endpoint

```bash
cd config
set MODEL_DATA_S3=s3://YOUR_BUCKET/.../output/model.tar.gz
python deploy_endpoint.py --model-data %MODEL_DATA_S3%
# or pass --model-data directly
```

Note the printed `ENDPOINT_NAME=...`. The model stays loaded on that instance until you delete the endpoint (AWS console: SageMaker → Endpoints).

## 3. Amazon SES setup

Use the **same AWS Region** everywhere (`AWS_REGION` in `.env`, Lambda, SageMaker endpoint, and SES). Example: `us-east-1`.

### 3a. Verify identities (console)

1. AWS Console → **Amazon SES** → make sure the **region** matches your stack (top-right).
2. **Configuration** (or **Identities** in newer UI) → **Create identity**.
3. **Sender (`REPORT_EMAIL_FROM`):**  
   - Easiest for testing: **Email address** → enter an address you can open (e.g. `reports@calljacob.com` or a no-reply on your domain).  
   - Or choose **Domain** for `calljacob.com` so any address on that domain can send (requires DNS records).
4. Complete verification (click the link in the email AWS sends, or complete DNS for domain).
5. **Recipient (`REPORT_EMAIL_TO`), e.g. `kritagya@calljacob.com`:**  
   - If your account is still in the **SES sandbox**, you **must** verify this address too: **Create identity** → **Email address** → `kritagya@calljacob.com` → confirm the verification email.  
   - To send to **any** address without verifying each one: SES → **Account dashboard** → **Request production access** (AWS may take hours to approve).

### 3b. Optional outbound from the same mailbox

If `REPORT_EMAIL_FROM` and `REPORT_EMAIL_TO` are the **same** mailbox, you still verify that address **once**; it can be both sender and recipient in sandbox.

### 3c. Test from your laptop (before Lambda)

From the `sagemaker/` folder, with `pip install -r requirements-dev.txt` and `.env` containing valid AWS keys plus:

```text
REPORT_EMAIL_FROM=verified-sender@yourdomain.com
REPORT_EMAIL_TO=kritagya@calljacob.com
AWS_REGION=us-east-1
```

Run:

```bash
python scripts/send_ses_test_email.py
```

The script prints a **`MessageId`** when SES **accepts** the message. That is not a guarantee the recipient’s mail server delivered it to the inbox.

If **`send_ses_test_email.py` succeeds** but you see **no mail**, run:

```bash
python scripts/ses_diagnose.py
```

Then check, in order:

1. **Spam / Junk / Promotions** (and “Quarantine” or admin digest if `calljacob.com` is hosted on Google Workspace / Microsoft 365).
2. **Correct region:** identities are per-region; sends use `AWS_REGION` in `.env`.
3. **Sandbox:** recipient must be **verified** unless you have production access (`ses_diagnose.py` hints at sandbox via low daily cap).
4. **Delay:** wait 5–15 minutes.
5. **SES bounce / complaint:** in the SES console, open your identities and look for metrics; configure SNS for bounces if you need visibility.

If this succeeds, SES and your IAM user allow `ses:SendRawEmail` from that `From` address. The Lambda role needs the same permission (see §4).

### 3d. 8:00 “every morning” and time zone

- **EventBridge Scheduler** fires at 08:00 in the **time zone you set** on the schedule (e.g. `America/New_York` or `Asia/Kolkata`), not “UTC 8:00” unless you choose `Etc/UTC`.
- Set Lambda env **`REPORT_TIMEZONE`** to the same IANA zone so the forecast “tomorrow” date inside the report matches your local calendar day (see §4 and §5).

## 4. Lambda function (container image)

From `sagemaker/lambda/daily_report` (Docker installed, ECR repo created):

```bash
aws ecr get-login-password --region YOUR_REGION | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.YOUR_REGION.amazonaws.com
docker build -t bike-daily-report .
docker tag bike-daily-report:latest YOUR_ACCOUNT.dkr.ecr.YOUR_REGION.amazonaws.com/bike-daily-report:latest
docker push YOUR_ACCOUNT.dkr.ecr.YOUR_REGION.amazonaws.com/bike-daily-report:latest
```

Create the function (replace ARNs and URIs):

```bash
aws lambda create-function ^
  --function-name bike-daily-demand-report ^
  --package-type Image ^
  --code ImageUri=YOUR_ACCOUNT.dkr.ecr.YOUR_REGION.amazonaws.com/bike-daily-report:latest ^
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-daily-report-role ^
  --timeout 120 ^
  --memory-size 512
```

### Lambda environment variables

| Variable | Example | Required |
|----------|---------|----------|
| `ENDPOINT_NAME` | `bike-demand-xgb-endpoint-1-2-1` | yes |
| `REPORT_EMAIL_FROM` | `reports@yourdomain.com` | yes |
| `REPORT_EMAIL_TO` | `you@gmail.com` | yes |
| `REPORT_TIMEZONE` | `America/New_York` | no (default) |
| `AWS_REGION` | `us-east-1` | set automatically on Lambda |
| `TARGET_DATE` | `2026-04-01` | no (only for tests) |

Update after create:

```bash
aws lambda update-function-configuration --function-name bike-daily-demand-report --environment "Variables={ENDPOINT_NAME=...,REPORT_EMAIL_FROM=...,REPORT_EMAIL_TO=...,REPORT_TIMEZONE=America/New_York}"
```

### Lambda IAM policy (execution role)

Attach an inline policy similar to:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": "sagemaker:InvokeEndpoint",
      "Resource": "arn:aws:sagemaker:YOUR_REGION:YOUR_ACCOUNT:endpoint/YOUR_ENDPOINT_NAME"
    },
    {
      "Effect": "Allow",
      "Action": "ses:SendRawEmail",
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "ses:FromAddress": "reports@yourdomain.com"
        }
      }
    }
  ]
}
```

Adjust `ses:FromAddress` or relax the condition while testing.

## 5. EventBridge Scheduler (8:00 local time daily)

Use **EventBridge Scheduler** (supports IANA time zones).

1. Create an IAM role **for the scheduler** that can invoke your Lambda (trust: `scheduler.amazonaws.com`).
2. Policy: `lambda:InvokeFunction` on `arn:aws:lambda:REGION:ACCOUNT:function:bike-daily-demand-report`.

Create the schedule (Console: EventBridge → Schedules → Create):

- **Schedule type**: Recurring → Cron expression (use the console builder) or **daily at 08:00**.
- **Time zone**: e.g. `America/New_York`.
- **Target**: AWS Lambda `bike-daily-demand-report`.

**CLI example (adjust schedule name, role, ARN):**

```bash
aws scheduler create-schedule --name bike-daily-8am ^
  --schedule-expression "cron(0 8 * * ? *)" ^
  --schedule-expression-timezone "America/New_York" ^
  --flexible-time-window Mode=OFF ^
  --target "{
    \"Arn\": \"arn:aws:lambda:us-east-1:ACCOUNT:function:bike-daily-demand-report\",
    \"RoleArn\": \"arn:aws:iam::ACCOUNT:role/EventBridgeSchedulerLambdaRole\"
  }" ^
  --state ENABLED
```

**Cron note:** In Scheduler, `cron(min hour day month day-of-week year)` uses the given `schedule-expression-timezone`.

## 6. Test without waiting for 8:00

Lambda console → **Test** with empty event `{}`, or CLI:

```bash
aws lambda invoke --function-name bike-daily-demand-report --payload "{}" out.json
type out.json
```

Optional one-off forecast date:

```bash
aws lambda update-function-configuration --function-name bike-daily-demand-report --environment "Variables={ENDPOINT_NAME=...,REPORT_EMAIL_FROM=...,REPORT_EMAIL_TO=...,TARGET_DATE=2026-07-01}"
aws lambda invoke ...
```

Remove `TARGET_DATE` afterward so production uses “tomorrow” in `REPORT_TIMEZONE`.

## 7. Regenerate weather profile JSON

After changing `data/raw/hour.csv`:

```bash
python scripts/generate_hourly_profile.py
```

Rebuild and push the Lambda Docker image so `hourly_profile.json` updates.

## Forecast scenario (limitation)

Hourly inputs use **median historical** `temp`, `hum`, `windspeed`, `weathersit` by hour (see `hourly_profile.json`). That is a **scenario**, not a live weather forecast. Swap in an API in `handler.py` later if you need real weather.
