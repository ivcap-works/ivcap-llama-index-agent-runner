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
ADD service.py runner.py events.py tool.py builtin_tools.py utils.py logger.py testing.py ./
ADD logging.json ./

# VERSION INFORMATION
ARG GIT_TAG=???
ARG GIT_COMMIT=??
ARG BUILD_DATE=???

ENV IVCAP_SERVICE_VERSION=$GIT_TAG
ENV IVCAP_SERVICE_COMMIT=$GIT_COMMIT
ENV IVCAP_SERVICE_BUILD=$BUILD_DATE
ENV VERSION="${GIT_TAG}|${GIT_COMMIT}|${BUILD_DATE}"

# Command to run
ENTRYPOINT ["python", "/app/service.py"]