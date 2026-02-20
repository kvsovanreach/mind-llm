FROM python:3.10-slim

WORKDIR /app

# Install Docker CLI for container management
RUN apt-get update && \
    apt-get install -y docker.io curl && \
    rm -rf /var/lib/apt/lists/*

# Create a group with GID 985 to match the docker socket
RUN groupadd -g 985 dockerhost && \
    usermod -aG dockerhost root

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python files
COPY *.py ./

# Run as root but with docker group access
USER root

EXPOSE 8001

# Remove --reload flag for production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
