FROM python:3.12-slim

WORKDIR /opt/passthrough

# Dependencies first - cached until pyproject.toml changes.
# Stub __init__.py satisfies hatchling so pip can build without real source.
COPY pyproject.toml ./
RUN mkdir -p passthrough && touch passthrough/__init__.py && \
    pip install --no-cache-dir . && \
    camoufox fetch && \
    playwright install-deps && \
    rm -rf /var/lib/apt/lists/*

# Project code - only this layer rebuilds on code changes
COPY passthrough/ ./passthrough/

# Non-root user for runtime
RUN useradd --create-home --shell /bin/bash app
USER app

EXPOSE 8191

CMD ["python", "-m", "uvicorn", "passthrough.main:app", "--host", "0.0.0.0", "--port", "8191"]
