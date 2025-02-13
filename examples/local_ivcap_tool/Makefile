SERVICE_TITLE=AI tool to check for prime numbers
SERVICE_NAME=is-prime-tool

TOOL_FILE=tool-service.py
TOOL_SCHEMA_FILE=is-prime.tool.json
IVCAP_SERVICE_FILE=service.json

GIT_COMMIT := $(shell git rev-parse --short HEAD)
GIT_TAG := $(shell git describe --abbrev=0 --tags ${TAG_COMMIT} 2>/dev/null || true)
VERSION="${GIT_TAG}|${GIT_COMMIT}|$(shell date -Iminutes)"

DOCKER_USER="$(shell id -u):$(shell id -g)"
DOCKER_DOMAIN=$(shell echo ${PROVIDER_NAME} | sed -E 's/[-:]/_/g')
DOCKER_NAME=$(shell echo ${SERVICE_NAME} | sed -E 's/-/_/g')
DOCKER_VERSION=${GIT_COMMIT}
DOCKER_TAG=${DOCKER_NAME}:${DOCKER_VERSION}
DOCKER_TAG_LOCAL=${DOCKER_NAME}:latest

PROJECT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
TARGET_PLATFORM := linux/amd64
RUN_DIR:=${PROJECT_DIR}/RUN
SERVICE_URL=http://localhost:8096
run:
	env VERSION=$(VERSION) \
		python ${PROJECT_DIR}/tool-service.py

test-local:
	curl -X POST -H "content-type: application/json" --data "{\"number\": 997}" http://localhost:8090

submit-request:
	curl -i -X POST \
		-H "Content-Type: application/json" \
		-H "X-Job-UUID: 00000000-0000-0000-0000-000000000000" \
		-H "X-Job-URL: ${SERVICE_URL}/00000000-0000-0000-0000-000000000000" \
		-d @${PROJECT_DIR}/test_query.json ${SERVICE_URL}
	curl -i --no-buffer -N ${SERVICE_URL}/00000000-0000-0000-0000-000000000000

install:
	pip install -r requirements.txt

docker-run: #docker-build
	docker run -it \
		-p 8090:8090 \
		--user ${DOCKER_USER} \
		--platform=${TARGET_PLATFORM} \
		--rm \
		${DOCKER_TAG_LOCAL}

docker-debug: #docker-build
	docker run -it \
		-p 8090:8090 \
		--user ${DOCKER_USER} \
		--platform=${TARGET_PLATFORM} \
		--entrypoint bash \
		${DOCKER_TAG_LOCAL}

docker-build:
	@echo "Building docker image ${DOCKER_NAME}"
	docker build \
		-t ${DOCKER_TAG_LOCAL} \
		--platform=${TARGET_PLATFORM} \
		--build-arg VERSION=${VERSION} \
		-f ${PROJECT_DIR}/Dockerfile \
		${PROJECT_DIR} ${DOCKER_BILD_ARGS}
	@echo "\nFinished building docker image ${DOCKER_NAME}\n"

SERVICE_IMG := ${DOCKER_DEPLOY}
PUSH_FROM := ""

docker-publish: docker-build
	@echo "Publishing docker image '${DOCKER_TAG}'"
	docker tag ${DOCKER_TAG_LOCAL} ${DOCKER_TAG}
	sleep 1
	$(eval size:=$(shell docker inspect ${DOCKER_TAG} --format='{{.Size}}' | tr -cd '0-9'))
	$(eval imageSize:=$(shell expr ${size} + 0 ))
	@echo "... imageSize is ${imageSize}"
	@if [ ${imageSize} -gt 2000000000 ]; then \
		set -e ; \
		echo "preparing upload from local registry"; \
		if [ -z "$(shell docker ps -a -q -f name=registry-2)" ]; then \
			echo "running local registry-2"; \
			docker run --restart always -d -p 8081:5000 --name registry-2 registry:2 ; \
		fi; \
		docker tag ${DOCKER_TAG} localhost:8081/${DOCKER_TAG} ; \
		docker push localhost:8081/${DOCKER_TAG} ; \
		$(MAKE) PUSH_FROM="localhost:8081/" docker-publish-common ; \
	else \
		$(MAKE) PUSH_FROM="--local " docker-publish-common; \
	fi

docker-publish-common:
	$(eval log:=$(shell ivcap package push --force ${PUSH_FROM}${DOCKER_TAG} | tee /dev/tty))
	$(eval registry := $(shell echo ${DOCKER_REGISTRY} | cut -d'/' -f1))
	$(eval SERVICE_IMG := $(shell echo ${log} | sed -E "s/.*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}.*) pushed/\1/"))
	@if [ "${SERVICE_IMG}" == "" ] || [ "${SERVICE_IMG}" == "${DOCKER_TAG}" ]; then \
		echo "service package push failed"; \
		exit 1; \
	fi
	@echo ">> Successfully published '${DOCKER_TAG}' as '${SERVICE_IMG}'"

service-register: docker-publish
	$(eval account_id=$(shell ivcap context get account-id))
	@if [[ ${account_id} != urn:ivcap:account:* ]]; then echo "ERROR: No IVCAP account found"; exit -1; fi
	$(eval service_id:=urn:ivcap:service:$(shell python3 -c 'import uuid; print(uuid.uuid5(uuid.NAMESPACE_DNS, \
        "${SERVICE_NAME}" + "${account_id}"));'))
	$(eval image:=$(shell ivcap package list ${DOCKER_TAG}))
	@if [[ -z "${image}" ]]; then echo "ERROR: No uploaded docker image '${DOCKER_TAG}' found"; exit -1; fi
	@echo "ServiceID: ${service_id}"
	cat ${PROJECT_DIR}/${IVCAP_SERVICE_FILE} \
	| sed 's|#DOCKER_IMG#|${image}|' \
	| sed 's|#SERVICE_ID#|${service_id}|' \
  | ivcap aspect update ${service_id} -f - --timeout 600

tool-register:
	$(eval account_id=$(shell ivcap context get account-id))
	@if [[ ${account_id} != urn:ivcap:account:* ]]; then echo "ERROR: No IVCAP account found"; exit -1; fi
	$(eval service_id:=urn:ivcap:service:$(shell python3 -c 'import uuid; print(uuid.uuid5(uuid.NAMESPACE_DNS, \
        "${SERVICE_NAME}" + "${account_id}"));'))
	@echo "ServiceID: ${service_id}"
	cat ${PROJECT_DIR}/${TOOL_SCHEMA_FILE} \
	| sed 's|#SERVICE_ID#|${service_id}|' \
  | ivcap aspect update ${service_id} -f - --timeout 600

FORCE:
