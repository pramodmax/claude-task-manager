FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
COPY src/ src/

RUN uv pip install --system -e .

VOLUME ["/data"]

ENV XDG_DATA_HOME=/data

EXPOSE 7654

CMD ["task-manager", "tui", "--no-browser", "--port", "7654"]
