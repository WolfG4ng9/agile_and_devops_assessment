FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir flask==3.1.2

COPY src/ ./src/

ENV PORT=5000
EXPOSE 5000

CMD ["python", "-m", "src.app"]
