FROM python:3.13-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
ENV UV_PYTHON=python3.13
RUN uv sync --frozen --no-dev --python 3.13

COPY . .

EXPOSE 8501

CMD [".venv/bin/streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
