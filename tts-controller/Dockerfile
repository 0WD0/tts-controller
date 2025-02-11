FROM python:3.9-slim

# Create docker group with same GID as host
RUN groupadd -g 999 docker

# Add default user to docker group
RUN usermod -aG docker root

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
