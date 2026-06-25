FROM python:3.12-slim

ENV MDREVIEW_DATA=/data \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    MDREVIEW_WEB_DIR=/app/web \
    PYTHONPATH=/app/src

WORKDIR /app
COPY src/ ./src/
COPY web/ ./web/

RUN mkdir -p /data
VOLUME /data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"

CMD ["python", "src/app.py"]
