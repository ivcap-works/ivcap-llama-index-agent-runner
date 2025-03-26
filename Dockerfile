FROM python:3.11-slim-bookworm AS builder

# Install required systems libraries
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  git sqlite3 && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install -U pip
COPY requirements.txt ./
RUN pip install -r requirements.txt

# COPY requirements-dev.txt ./
# RUN pip install -r requirements-dev.txt --force-reinstall

# Get service files
ADD service.py events.py tool.py builtin_tools.py utils.py testing.py ./

# VERSION INFORMATION
ARG VERSION ???
ENV VERSION=$VERSION

# Command to run
ENTRYPOINT ["python", "/app/service.py"]