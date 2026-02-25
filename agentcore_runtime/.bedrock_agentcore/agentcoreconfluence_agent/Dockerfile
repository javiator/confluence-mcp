FROM public.ecr.aws/docker/library/python:3.10-slim

WORKDIR /app

# Install Bedrock SDK and dependencies
COPY pyproject.toml .
# We use uv to install the packages simply as a best practice but pip would work here too
RUN pip install "uv>=0.4.0" \
    && uv pip install --system ".[all]"

# Copy application source code
COPY ./src /app/src

CMD ["python", "src/main.py"]
