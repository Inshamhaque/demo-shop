# The demo shop as a service. The backend reads its logs and metrics through the MCP stand-in,
# so the shop writes its log to a folder the host can see (mounted at /app/logs by docker-compose.yml).
FROM python:3.13-slim

WORKDIR /app
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8100

CMD ["python", "-m", "service.server", "--host", "0.0.0.0", "--port", "8100", "--log", "/app/logs/shop.log"]
