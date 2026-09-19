FROM python:3.12-slim

RUN pip install --no-cache-dir \
    pytest==8.* \
    numpy \
    pandas \
    openpyxl \
    python-docx \
    python-pptx \
    reportlab \
    matplotlib

WORKDIR /workspace

RUN useradd --create-home --uid 1000 runner
USER runner

CMD ["python", "--version"]
