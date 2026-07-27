FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /var/task

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Lambda Web Adapter extension
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1 /lambda-adapter /opt/extensions/lambda-adapter

# Adapter + app port
ENV AWS_LWA_PORT=8080
ENV PORT=8080
ENV AWS_LWA_READINESS_CHECK_PATH=/
ENV AWS_LWA_REMOVE_BASE_PATH=/chat

# Start FastAPI HTTP server (no Mangum handler needed)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]