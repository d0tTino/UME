# Use an official Python runtime as a parent image, matching project's Python version
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed by Poetry or project dependencies
# (e.g., gcc, libffi-dev for some packages, though maybe not for this specific set)
# For now, keeping it minimal. Add if build errors occur for specific packages.
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*

# Install Poetry
# Using pip directly to install poetry to avoid needing to install pipx or other tools first
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir poetry==1.7.1 # Pinning Poetry version for reproducibility

# Copy only files necessary for installing dependencies first, to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Configure Poetry to not create virtual environments within the project directory
# and install dependencies into the system's site-packages.
# This is a common practice for Docker images to keep them leaner.
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-dev
    # --no-dev: Do not install development dependencies like pytest, ruff for production image

# Copy the rest of the application code into the container
COPY . .
# This includes src/ for the ume library and app.py for the API

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application using Uvicorn
# CMD ["poetry", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
# Alternative CMD if poetry install puts uvicorn in PATH correctly (it should with virtualenvs.create false)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```
