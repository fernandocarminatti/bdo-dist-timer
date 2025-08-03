FROM python:3.12-alpine AS builder
WORKDIR /app
RUN apk add --no-cache gcc musl-dev libffi-dev
RUN pip install --no-cache-dir --prefix=/install websockets
# ===========
FROM python:3.12-alpine AS final
WORKDIR /app
COPY --from=builder /install /usr/local
COPY server.py cert.pem key.pem .

EXPOSE 443
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "443"]
