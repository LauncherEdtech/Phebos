FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY config.yaml ./

# Banco de dados fica num volume montado em /app/data
ENV PIXZAP_DATA_DIR=/app/data
ENV PIXZAP_CONFIG=/app/config.yaml

CMD ["python", "-m", "pixzap.main"]
