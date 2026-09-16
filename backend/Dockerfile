FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ gfortran libopenblas-dev liblapack-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

EXPOSE 8001

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001} --workers 1
