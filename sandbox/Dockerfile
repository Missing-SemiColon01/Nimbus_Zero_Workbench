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

COPY pptx_helpers.py /opt/sandbox/pptx_helpers.py
COPY docx_helpers.py /opt/sandbox/docx_helpers.py
COPY pdf_helpers.py /opt/sandbox/pdf_helpers.py
ENV PYTHONPATH=/opt/sandbox

WORKDIR /workspace

RUN useradd --create-home --uid 1000 runner
USER runner

CMD ["python", "--version"]
