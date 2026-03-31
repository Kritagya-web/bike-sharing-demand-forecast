# AWS Lambda container image for daily_report
FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt -t "${LAMBDA_TASK_ROOT}"

COPY handler.py hourly_profile.json ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
