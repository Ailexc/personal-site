FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0 python-multipart==0.0.20

COPY main.py /app/main.py
COPY templates /app/templates

ENV RESUME_CODE=0000
EXPOSE 8791

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8791", "--proxy-headers", "--forwarded-allow-ips", "*"]
