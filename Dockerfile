# Agent Simulator — official image
#
# Build:
#   docker build -t agent-simulator:latest .
#
# Run (against an already-running OTel Collector on host port 4317):
#   docker run --rm \
#     -e OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4317 \
#     agent-simulator:latest
#
# Run with a custom config:
#   docker run --rm \
#     -v $(pwd)/config:/app/config \
#     agent-simulator:latest --config config/my_agent.yaml

FROM python:3.11-slim

# Install build dependencies for grpcio (needed by OTLP gRPC exporter)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what pip needs first so the layer is cached on code-only changes
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/

RUN pip install --no-cache-dir -e .

# Non-root user for security
RUN useradd --system --no-create-home simulator
USER simulator

ENTRYPOINT ["agent-simulator"]
CMD ["--config", "config/default.yaml"]
