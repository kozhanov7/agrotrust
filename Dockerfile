# Image with the agrometrics command line tool.
# Build:  docker build -t agrotrust-metrics .
# Run:    docker run --rm -v "$PWD/data:/data" agrotrust-metrics simulate --out /data

FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /dist

FROM python:3.12-slim
LABEL org.opencontainers.image.title="agrotrust-metrics" \
      org.opencontainers.image.description="Reliability metrics for IoT agricultural monitoring data" \
      org.opencontainers.image.source="https://github.com/kozhanov7/agrotrust" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl \
    && useradd --create-home --uid 1000 agro \
    && mkdir /data && chown agro /data

COPY examples /app/examples
WORKDIR /data
USER agro

ENTRYPOINT ["agrometrics"]
CMD ["--help"]
