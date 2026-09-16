FROM python:3.12-slim

RUN pip install --no-cache-dir pytest==8.* numpy pandas 2>/dev/null || true

WORKDIR /workspace

RUN useradd --create-home --uid 1000 runner
USER runner

CMD ["python", "--version"]
