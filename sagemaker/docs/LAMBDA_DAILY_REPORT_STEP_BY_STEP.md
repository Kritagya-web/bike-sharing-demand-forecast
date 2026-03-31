# Step-by-step: Daily email report (Lambda + Docker + EventBridge)

Goal: go from **“SageMaker endpoint and SES work”** to **“Lambda runs every morning at 8:00 and emails a forecast.”**  
The steps match the code in [`lambda/daily_report/`](../lambda/daily_report/).

**Deliverables**

1. A **Docker image** with your Lambda code.  
2. An **ECR** repository in AWS to store that image.  
3. A **Lambda function** that pulls the image, calls your **SageMaker endpoint**, builds an Excel file, and sends **email via SES**.  
4. An **EventBridge schedule** that triggers Lambda every day at **8:00** in a timezone you choose.

**Important:** Use the **same AWS Region** for everything (example below uses `us-east-1`): SageMaker endpoint, SES identities, ECR, Lambda, and Scheduler.

---

## Before you start (checklist)

| Requirement | Why |
|-------------|-----|
| SageMaker **endpoint** is **In service** | Lambda invokes it by name. |
| **SES** sender and (if sandbox) recipient are **verified** in that region | Otherwise email fails. |
| **Docker Desktop** installed and running (Windows) | To build the container image. |
| **AWS CLI** installed (`aws --version`) | To log in to ECR and push the image. |
| AWS CLI configured (`aws configure`) with an IAM user that can create ECR, Lambda, IAM roles (or use console for everything except Docker push). | You need permissions to push to ECR and create Lambda. |

**Write down these values** (you will paste them many times):

- **Region** — e.g. `us-east-1`  
- **AWS account ID** — 12 digits (AWS Console: click your name (top right) → **Account**; or run `aws sts get-caller-identity` in a terminal).  
- **SageMaker endpoint name** — e.g. `bike-demand-xgb-endpoint-1-2-1` (SageMaker console → **Inference** → **Endpoints**).  
- **Verified `REPORT_EMAIL_FROM`** and **`REPORT_EMAIL_TO`** — exactly as in SES in that region.

---

## Part A — Create an ECR repository

Amazon **ECR** is like Docker Hub but private inside your AWS account.

1. Open **AWS Console** → set region (top right) to e.g. **N. Virginia** (`us-east-1`).  
2. Search for **ECR** (Elastic Container Registry).  
3. Open **Repositories** (under *Private registry*).  
4. Click **Create repository**.  
5. **Visibility settings:** Private.  
6. **Repository name:** e.g. `bike-daily-report` (no spaces).  
7. Leave other defaults → **Create repository**.

**Copy the repository URI** shown after creation. It looks like:

`123456789012.dkr.ecr.us-east-1.amazonaws.com/bike-daily-report`

You will use it as **`<ECR_URI_WITHOUT_TAG>`** below (no `:latest` yet).

---

## Part B — Build the Docker image on your computer

1. **Start Docker Desktop** and wait until it says it is running.

2. Open **PowerShell**.

3. Go to the **daily_report** folder (inside your project):

   ```powershell
   cd path\to\your\repo\sagemaker\lambda\daily_report
   ```

   If your path differs, use the folder that contains `Dockerfile` and `handler.py`.

4. **Build** the image (this can take a few minutes the first time).

   Lambda expects a **linux/amd64** image and a **manifest** format it understands. Use this so you avoid *“image manifest … media type … not supported”* when creating/updating the function:

   ```powershell
   docker build --platform linux/amd64 --provenance=false --sbom=false -t bike-daily-report .
   ```

   - If your Docker reports an **unknown flag** for `provenance` / `sbom`, use legacy BuildKit instead, then build:
     ```powershell
     $env:DOCKER_BUILDKIT="0"
     docker build --platform linux/amd64 -t bike-daily-report .
     ```
   - When you create the Lambda, set **Architecture** to **x86_64** (default) to match `linux/amd64`.

   The final line should mention **successfully built** or **done**. If Docker says “cannot connect”, ensure Docker Desktop is running.

You now have a local image named `bike-daily-report`.

---

## Part C — Log in to ECR and push the image

Replace **`ACCOUNT_ID`** and **`REGION`** with yours. Replace the URL host with the one from your ECR repo if different.

1. **Log Docker into ECR** (PowerShell):

   ```powershell
   aws ecr get-login-password --region REGION | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com
   ```

   Example for `us-east-1` and account `123456789012`:

   ```powershell
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
   ```

   You should see **Login Succeeded**.

2. **Tag** your local image so it matches the ECR repository:

   ```powershell
   docker tag bike-daily-report:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/bike-daily-report:latest
   ```

3. **Push**:

   ```powershell
   docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/bike-daily-report:latest
   ```

When this finishes, the **Image** tag `latest` appears in the ECR repository in the console.

---

## Part D — IAM role for Lambda (execution role)

Lambda needs permission to **write logs**, **call your SageMaker endpoint**, and **send email via SES**.

### D.1 Create the role

1. AWS Console → **IAM** → **Roles** → **Create role**.  
2. **Trusted entity:** **AWS service** → **Lambda** → **Next**.  
3. **Add permissions:** search for **AWSLambdaBasicExecutionRole** → check it → **Next**.  
   - This allows CloudWatch Logs (`logs:CreateLogGroup`, etc.).  
4. **Role name:** e.g. `bike-daily-report-lambda-role` → **Create role**.

### How to find `YOUR_ENDPOINT_NAME` (for the JSON below)

You only need the **endpoint name** text (not the full URL SageMaker shows for invoke). Lambda’s **`ENDPOINT_NAME`** environment variable uses this **same** string.

**If the left menu only shows “Domains” / “Associated domains” and there is no Inference section:**  
You are in a **narrow** SageMaker view. Do any of the following:

- Click the **← back** arrow or **Amazon SageMaker** title at the top of the left sidebar until you see a broader menu, **or**
- In the top search bar, type **`Endpoints`** or **`SageMaker endpoints`** and open the result for **Amazon SageMaker** (inference endpoints), **or**
- Open this direct link (change `us-east-1` if you use another region):  
  [Endpoints in us-east-1](https://us-east-1.console.aws.amazon.com/sagemaker/home?region=us-east-1#/endpoints)

**Console steps (typical layout):**

1. AWS Console → **SageMaker** (make sure the **region** at top-right matches where you deployed, e.g. `N. Virginia` / `us-east-1`).  
2. Left menu → **Inference** → **Endpoints** (on some screens this appears under **Amazon SageMaker AI** — use the link above if your sidebar is minimal).  
3. In the table, find your endpoint in the **Endpoint name** column (e.g. `bike-demand-xgb-endpoint-1-2-1`).  
4. Check **Status** is **In service**. Copy the name **exactly** (no spaces).

**Turn that into the IAM `Resource` ARN:**

```text
arn:aws:sagemaker:<REGION>:<ACCOUNT_ID>:endpoint/<ENDPOINT_NAME>
```

Example: endpoint `bike-demand-xgb-endpoint-1-2-1` in `us-east-1` for account `123456789012`:

`arn:aws:sagemaker:us-east-1:123456789012:endpoint/bike-demand-xgb-endpoint-1-2-1`

**Account ID** is the same 12-digit value as in your ECR host (`123456789012.dkr.ecr...`). Confirm under the console account menu → **Account**, or `aws sts get-caller-identity`.

**CLI alternative:**

```powershell
aws sagemaker list-endpoints --region us-east-1 --query "Endpoints[*].[EndpointName,EndpointStatus]" --output table
```

### D.2 Add SageMaker + SES (inline policy)

1. Open the role you just created → **Permissions** → **Add permissions** → **Create inline policy** → **JSON** tab.  
2. Paste this JSON and **replace** `REGION`, `ACCOUNT_ID`, `YOUR_ENDPOINT_NAME`, and **`your-verified-sender@example.com`** with your values (see **How to find YOUR_ENDPOINT_NAME** above for the SageMaker line):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sagemaker:InvokeEndpoint",
      "Resource": "arn:aws:sagemaker:REGION:ACCOUNT_ID:endpoint/YOUR_ENDPOINT_NAME"
    },
    {
      "Effect": "Allow",
      "Action": "ses:SendRawEmail",
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "ses:FromAddress": "your-verified-sender@example.com"
        }
      }
    }
  ]
}
```

- **Example** endpoint resource:

  `arn:aws:sagemaker:us-east-1:123456789012:endpoint/bike-demand-xgb-endpoint-1-2-1`

3. **Review** → name the policy e.g. `BikeDailyReportSagemakerSes` → **Create policy**.

If Lambda gets “access denied” on email, try temporarily removing the `"Condition"` block under `ses:SendRawEmail`, then add it back once sends succeed.

---

## Part E — Create the Lambda function (container image)

1. AWS Console → **Lambda** → **Create function**.  
2. Choose **Container image**.  
3. **Function name:** e.g. `bike-daily-demand-report`.  
4. **Container image URI:** **Browse** → select your ECR repo `bike-daily-report` → image tag **`latest`**.  
5. **Architecture:** leave **x86_64** (default for this image unless you changed it).  
6. Expand **Change default execution role** → **Use an existing role** → select **`bike-daily-report-lambda-role`** (the role from Part D).  
7. **Create function**.

### E.1 Configuration (timeout and memory)

On the function page → **Configuration** → **General configuration** → **Edit**:

- **Timeout:** `1 min 0 sec` is tight; use **2 min 0 sec** (`120` seconds).  
- **Memory:** **512 MB** is enough for this code.  
- Save.

### E.2 Environment variables

**Configuration** → **Environment variables** → **Edit** → add:

| Key | Value | Notes |
|-----|-------|--------|
| `ENDPOINT_NAME` | Your endpoint name | Must match SageMaker exactly. |
| `REPORT_EMAIL_FROM` | Verified SES sender | Same as in `ses:FromAddress` policy if you used the condition. |
| `REPORT_EMAIL_TO` | Where reports go | Must be verified if SES is still in sandbox. |
| `REPORT_TIMEZONE` | e.g. `America/New_York` | Defines “tomorrow” for the forecast. Use [IANA time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). |

**Optional (testing only):**

| Key | Value |
|-----|--------|
| `TARGET_DATE` | `2026-04-01` | Overrides “tomorrow” for one-off tests. Remove later for production. |

**Note:** Lambda sets `AWS_REGION` automatically; you do not need to add it unless you rely on code that reads only that key (this project uses the runtime region).

Save.

---

## Part F — Test Lambda (do this before scheduling)

1. In Lambda → **Test** → **Create new event** → Event name: `empty` → template: **hello-world** or blank JSON → set body to:

   ```json
   {}
   ```

2. **Save** → **Test**.

**Success:** **Execution result: succeeded** (green). Check your email (and **Junk**) for the Excel report.

**Failure:** Open **Monitor** → **View CloudWatch logs** (or **Logs** tab). Read the error:

- `AccessDeniedException` on **SageMaker** → fix the endpoint ARN in the IAM policy or `ENDPOINT_NAME`.  
- SES error → verify identities and `ses:SendRawEmail`.  
- Timeout → increase timeout to 120 s.

**CLI test** (optional):

```powershell
aws lambda invoke --function-name bike-daily-demand-report --region REGION --payload "{}" out.json
Get-Content out.json
```

---

## Part G — Run every morning at 8:00 (EventBridge Scheduler)

Scheduler needs **its own** IAM role that is allowed to **invoke** your Lambda.

### G.1 Role for the scheduler

This role is **only** for **EventBridge Scheduler** (the service that runs your cron). It is **not** the same as **EventBridge → API destinations**.

**IAM uses two different JSON documents — do not mix them up:**

| Where in the console | What it is | Contains |
|---------------------|------------|----------|
| **Step 1: Custom trust policy** (while creating the role), **or** role → **Trust relationships** → **Edit trust policy** | **Trust policy** | `"Principal": { "Service": "scheduler.amazonaws.com" }` and `"Action": "sts:AssumeRole"` |
| **Permissions** → **Add permissions** → **Create inline policy** → JSON | **Permissions (identity) policy** | `"Action": "lambda:InvokeFunction"` and `"Resource": "arn:aws:lambda:..."` — **no `Principal` key** |

If you paste the **trust** JSON into an **inline policy** editor, you get errors like *“IDENTITY_POLICY does not support the Principal element”* and *“Missing Resource”*. Fix: use **trust** JSON only under **Trust relationships**; use the **`lambda:InvokeFunction`** JSON only under **Permissions**.

**Trusted entity (pick one method):**

**Method A — Use case list (if you see it)**  

1. **IAM** → **Roles** → **Create role**.  
2. **Trusted entity type:** **AWS service**.  
3. Open the **Use case** dropdown and type **`Scheduler`** or scroll until you find **EventBridge Scheduler** (sometimes listed exactly like that, not plain “EventBridge”).  
4. Select the use case that says Scheduler can assume the role → **Next**.  
5. On the permissions step, if AWS suggests a policy for invoking Lambda, you can use it; otherwise choose **Next** with no extra permissions and after the role exists add the **`lambda:InvokeFunction`** inline policy shown in Method B.

**Method B — Custom trust policy (works when “Scheduler” is hard to find)**  

1. **IAM** → **Roles** → **Create role**.  
2. **Trusted entity type:** **Custom trust policy**.  
3. Paste this JSON (nothing to edit):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "scheduler.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

4. **Next**. On **Add permissions**, you may **skip** all managed policies (nothing checked) → **Next** → enter role name → **Create role**.

5. **After** the role exists, open it → **Permissions** tab → **Add permissions** → **Create inline policy** → **JSON** → paste **only** this (permissions policy — **not** the trust policy):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:bike-daily-demand-report"
    }
  ]
}
```

Replace `REGION`, `ACCOUNT_ID`, and the function name if yours differ → **Review** → name e.g. `InvokeBikeDailyLambda` → **Create policy**.

**If the role shows “Permissions policies (0)”:** that is normal right after **Create role** with no managed policies selected. It does **not** mean role creation failed. Add the **inline policy** above (`lambda:InvokeFunction`). If **Add permissions** → **Create inline policy** fails with **Access denied**, then your IAM user needs `iam:PutRolePolicy` (or an admin must attach the policy).

**Also verify:** **Trust relationships** tab must allow **`scheduler.amazonaws.com`** to assume the role (see the trust JSON in Method B). If it still says `events.amazonaws.com` or something else, **Edit trust policy** and fix it.

**What to avoid:** **EventBridge** with use case **API destinations** — that sets the wrong trusted service (`events.amazonaws.com` / API-destination flow), not **`scheduler.amazonaws.com`**.

### G.2 Create the schedule

1. AWS Console → **Amazon EventBridge** → **Schedules** (under *Scheduler*).  
2. **Create schedule**.  
3. **Schedule name:** e.g. `bike-daily-8am`.  
4. **Schedule pattern:** Recurring → **Cron expression**.  
   - For **every day at 08:00** in a chosen timezone, use:  
     `cron(0 8 * * ? *)`  
   - **Timezone:** pick yours, e.g. `America/New_York`, `Asia/Kolkata`, etc. (must match how you think about “8 am”).  
5. **Target:** **AWS Lambda** → select **`bike-daily-demand-report`**.  
6. **Execution role:** the role from G. **1** (scheduler invoke role).  
7. **Create schedule**.

**Cron reminder:** The **hour** `8` is in the **schedule’s timezone**, not UTC (unless you choose a UTC zone).

---

## Part H — Align “8 am” with the report’s date

- **Scheduler** decides **when** Lambda runs.  
- **`REPORT_TIMEZONE`** inside Lambda decides what **calendar day** is used as “tomorrow” for the forecast.

Use the **same** timezone for both if you want “every morning at 8 in Chicago” to match “tomorrow in Chicago.”

---

## Troubleshooting (quick)

| Symptom | What to check |
|--------|----------------|
| Docker build fails | Run from folder containing `Dockerfile`; Docker Desktop running. |
| `docker push` denied | ECR login again; correct account/region in tag. |
| Lambda: SageMaker error | Endpoint **In service**; same region; `ENDPOINT_NAME` exact; IAM `InvokeEndpoint` on that endpoint ARN. |
| Lambda: SES error | Verified From/To (sandbox); region matches; IAM `SendRawEmail`. |
| No email but Lambda succeeds | Junk folder; try `REPORT_EMAIL_TO` = your Gmail to isolate filtering. |
| Schedule never runs | Schedule **Enabled**; scheduler role has `lambda:InvokeFunction`; correct region. |
| **The image manifest / media type is not supported** | Rebuild with `--platform linux/amd64 --provenance=false --sbom=false`, then **tag + push** a new `latest` (or new tag) and **re-deploy** the Lambda image. Lambda must be **x86_64** unless you intentionally built `linux/arm64` for **arm64** Lambda. |
| **Policy error: Principal not supported / Missing Resource** | You put a **trust policy** into **Permissions** → inline policy. Trust JSON belongs under **Trust relationships** only; permissions JSON must use `lambda:InvokeFunction` + `Resource` only (see Part G.1 table). |

---

## After you change `hour.csv` or scenario logic

Regenerate the profile and rebuild the image:

```powershell
cd "...\sagemaker"
python scripts\generate_hourly_profile.py
cd lambda\daily_report
docker build --platform linux/amd64 --provenance=false --sbom=false -t bike-daily-report .
# tag + push again (Part C)
```

Then in Lambda you can **Deploy** a new image revision, or update the function’s image tag to the new `latest` in ECR.

---

## Related docs

- Overview and CLI shortcuts: [`AWS_DAILY_REPORT.md`](AWS_DAILY_REPORT.md)  
- SES testing: `python scripts/send_ses_test_email.py` from the `sagemaker/` folder
