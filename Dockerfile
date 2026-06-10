FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY config.yaml ./

# Banco de dados e kill switch ficam num volume montado em /app/data
ENV PHEBOS_DATA_DIR=/app/data
# Caminho explícito do config (o pacote é instalado em site-packages, então
# o cálculo relativo ao módulo não acha o config.yaml — apontamos direto)
ENV PHEBOS_CONFIG=/app/config.yaml

CMD ["python", "-m", "phebos.main", "run"]
