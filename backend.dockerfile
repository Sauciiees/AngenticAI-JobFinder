FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Virtual screen for the visible browser windows, shared as a web page (noVNC),
# and Thai fonts so job pages render readably for the vision agent.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb x11vnc novnc websockify \
        fonts-thai-tlwg fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application
COPY . .
RUN sed -i 's/\r$//' docker/start.sh && chmod +x docker/start.sh

# 8000: API and web app. 6080: live browser view (noVNC)
EXPOSE 8000 6080

CMD ["./docker/start.sh"]
