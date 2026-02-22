# Use the official Python managed image for Lambda or a slim debian base
# Using slim-buster for compatibility with the Lambda Web Adapter
FROM python:3.11-slim

# Copy Lambda Web Adapter binary from the official ECR image
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

# Install dependencies
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY src/ src/

# Copy configuration
COPY config.json .

# Configuration for Lambda Web Adapter
ENV PORT=8000
ENV PYTHONPATH="/app/src"
ENV READINESS_CHECK_PATH="/health"

# Expose port (metadata)
EXPOSE 8000

# Start the uvicorn server
# The Web Adapter will proxy Lambda events to this HTTP server
CMD ["uvicorn", "confluence_mcp.http_server.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]
