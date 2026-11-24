ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.22
FROM ${BUILD_FROM}

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install su-exec to drop root privileges after bashio reads add-on options
RUN apk add --no-cache su-exec \
    && adduser -D -H appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code (read-only for appuser)
COPY main.py .
RUN chown -R root:root /app && chmod -R a+rX /app

# Copy startup script
COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
