SERVICE_NAME=crew-ai-service
SERVICE_TITLE=Execute a crewAI instruction set

SERVICE_FILE=crew_ai_service.py
PROVIDER_NAME=sc.experimental

SERVICE_ID:=ivcap:service:$(shell python3 -c 'import uuid; print(uuid.uuid5(uuid.NAMESPACE_DNS, \
        "${PROVIDER_NAME}" + "${SERVICE_NAME}"));')

GIT_COMMIT := $(shell git rev-parse --short HEAD)
GIT_TAG := $(shell git describe --abbrev=0 --tags ${TAG_COMMIT} 2>/dev/null || true)
VERSION="${GIT_TAG}|${GIT_COMMIT}|$(shell date -Iminutes)"

DOCKER_USER="$(shell id -u):$(shell id -g)"
DOCKER_DOMAIN=$(shell echo ${PROVIDER_NAME} | sed -E 's/[-:]/_/g')
DOCKER_NAME=$(shell echo ${SERVICE_NAME} | sed -E 's/-/_/g')
DOCKER_VERSION=${GIT_COMMIT}
DOCKER_TAG=${DOCKER_NAME}:${DOCKER_VERSION}
DOCKER_TAG_LOCAL=${DOCKER_NAME}:latest
TARGET_PLATFORM=linux/$(shell go env GOARCH)

PROJECT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
RUN_DIR = ${PROJECT_DIR}/_run_

TMP_DIR=/tmp
DOCKER_LOCAL_DATA_DIR=${PROJECT_DIR}/_run_

#OPEN_ARTIFACT_POLICY=urn:ivcap:policy:4b801b57-4c9b-515a-b545-5929de708fbf

HOST=localhost
PORT=8096
SERVICE_URL=http://${HOST}:${PORT}
MAX_WAIT=10

run:
	env VERSION=$(VERSION) \
	python service.py --host ${HOST} --port ${PORT} --max-wait ${MAX_WAIT} --testing

# run-http:
# 	mkdir -p ${RUN_DIR} && rm -f ${RUN_DIR}/log.txt
# 	env IVCAP_OUT_DIR=${RUN_DIR} \
# 	python ${SERVICE_FILE} \
# 		--ivcap:service-url ${SERVICE_URL}

submit-request:
	curl -X POST -H "Content-Type: application/json" -d @${PROJECT_DIR}/examples/simple_query.json ${SERVICE_URL}

build:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

clean:
	rm -rf ${RUN_DIR}
	rm -rf db
	rm log.txt

docker-run: #docker-build
	@echo ""
	@echo ">>>>>>> On Mac, please ensure that this directory is mounted into minikube (if that's what you are using)"
	@echo ">>>>>>>    minikube mount ${PROJECT_DIR}:${PROJECT_DIR}"
	@echo ""
	mkdir -p ${RUN_DIR} && rm -rf ${RUN_DIR}/*
	docker run -it \
		-e IVCAP_INSIDE_CONTAINER="" \
		-e IVCAP_ORDER_ID=ivcap:order:0000 \
		-e IVCAP_NODE_ID=n0 \
		-e IVCAP_IN_DIR=/data/in \
		-e IVCAP_OUT_DIR=/data/out \
		-e IVCAP_CACHE_DIR=/data/cache \
		-v ${PROJECT_DIR}/examples:/data/in \
		-v ${RUN_DIR}:/data/out \
		-v ${RUN_DIR}:/data/cache \
		--user ${DOCKER_USER} \
		${DOCKER_NAME} \
			--input /data/in/queue \
			--output urn:ivcap:queue:/data/out
	@echo ">>> Output should be in '${DOCKER_LOCAL_DATA_DIR}' (might be inside minikube)"

docker-debug: #docker-build
	# If running Minikube, the 'data' directory needs to be created inside minikube
	mkdir -p ${DOCKER_LOCAL_DATA_DIR}/in ${DOCKER_LOCAL_DATA_DIR}/out
	docker run -it \
		-e IVCAP_INSIDE_CONTAINER="" \
		-e IVCAP_ORDER_ID=ivcap:order:0000 \
		-e IVCAP_NODE_ID=n0 \
		-v ${PROJECT_DIR}:/data\
		--user ${DOCKER_USER} \
		--entrypoint bash \
		${DOCKER_TAG_LOCAL}

docker-build:
	@echo "Building docker image ${DOCKER_NAME}"
	@echo "====> DOCKER_REGISTRY is ${DOCKER_REGISTRY}"
	@echo "====> LOCAL_DOCKER_REGISTRY is ${LOCAL_DOCKER_REGISTRY}"
	@echo "====> TARGET_PLATFORM is ${TARGET_PLATFORM}"
	DOCKER_BUILDKIT=1 docker build \
		-t ${DOCKER_NAME} \
		--platform=${TARGET_PLATFORM} \
		--build-arg GIT_COMMIT=${GIT_COMMIT} \
		--build-arg GIT_TAG=${GIT_TAG} \
		--build-arg BUILD_DATE="$(shell date)" \
		-f ${PROJECT_DIR}/Dockerfile \
		${PROJECT_DIR} ${DOCKER_BILD_ARGS}
	@echo "\nFinished building docker image ${DOCKER_NAME}\n"

# docker-run-data-proxy: #docker-build
# 	rm -rf /tmp/order1
# 	mkdir -p /tmp/order1/in
# 	mkdir -p /tmp/order1/out
# 	docker run -it \
# 		-e IVCAP_INSIDE_CONTAINER="Yes" \
# 		-e IVCAP_ORDER_ID=ivcap:order:0000 \
# 		-e IVCAP_NODE_ID=n0 \
# 		-e http_proxy=http://192.168.0.226:9999 \
# 	  -e https_proxy=http://192.168.0.226:9999 \
# 		-e IVCAP_STORAGE_URL=http://artifact.local \
# 	  -e IVCAP_CACHE_URL=http://cache.local \
# 		${DOCKER_NAME} \
# 		--crew urn:ivcap:artifact:16837369-e7ee-4f38-98cd-d2d056f5e148 \
# 		--p1 recycling \
# 		--p2 "plastics in ocean"

FORCE: run
.PHONY: run
