FROM python:3.12-slim

WORKDIR /app

# Copy and install requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

EXPOSE 8000

# Start FastAPI
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]