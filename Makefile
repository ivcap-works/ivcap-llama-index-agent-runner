SERVICE_TITLE=LLamaIndex Agent Runner
SERVICE_NAME=llama-index-agent-runner

TOOL_FILE=service.py
IVCAP_SERVICE_FILE=service.json

PORT=8085
HOST=localhost
SERVICE_URL=http://${HOST}:8099
HTTP_PROXY=http://${HOST}:9999

include Makefile.common

run:
	env VERSION=$(VERSION) PYTHONPATH="" \
		python ${PROJECT_DIR}/${TOOL_FILE} --port ${PORT}

run-with-proxy:
	env VERSION=$(VERSION) PYTHONPATH="" \
		http_proxy=${HTTP_PROXY} \
		python ${PROJECT_DIR}/${TOOL_FILE} --port ${PORT}

run-litellm:
	env $(shell cat .env | xargs) litellm --port 4000 -m gpt-3.5-turbo -m gpt-4

test-simple:
	TOKEN=$(shell ivcap context get access-token --refresh-token); \
	curl -i -X POST \
	-H "content-type: application/json" \
	-H "Timeout: 60" \
	-H "Authorization: Bearer $$TOKEN" \
	--data @${PROJECT_DIR}/tests/simple_query.json \
	http://${HOST}:${PORT}

test-is-prime:
	TOKEN=$(shell ivcap context get access-token --refresh-token); \
	curl -i -X POST \
	-H "content-type: application/json" \
	-H "Timeout: 600" \
	-H "Authorization: $$TOKEN" \
	--data @${PROJECT_DIR}/tests/is_prime.json \
	http://${HOST}:${PORT}

test-is-prime-minikube:
	TOKEN=$(shell ivcap --context minikube context get access-token --refresh-token); \
	curl -i -X POST \
	-H "content-type: application/json" \
	-H "Timeout: 10" \
	-H "Authorization: Bearer $$TOKEN" \
	--data @${PROJECT_DIR}/tests/is_prime.json \
	http://ivcap.minikube/1/services2/${SERVICE_ID}/jobs

test-is-prime-ivcap:
	TOKEN=$(shell ivcap --context gke-dev context get access-token --refresh-token); \
	curl -i -X POST \
	-H "content-type: application/json" \
	-H "Timeout: 10" \
	-H "Authorization: Bearer $$TOKEN" \
	--data @${PROJECT_DIR}/tests/is_prime.json \
	https://develop.ivcap.net/1/services2/${SERVICE_ID}/jobs

JOB_ID=00000000-0000-0000-0000-000000000000
test-get-result-ivcap:
	TOKEN=$(shell ivcap --context gke-dev context get access-token --refresh-token); \
	curl \
	-H "content-type: application/json" \
	-H "Timeout: 20" \
	-H "Authorization: Bearer $$TOKEN" \
	https://develop.ivcap.net/1/services2/${SERVICE_ID}/jobs/${JOB_ID}?with-result-content=true | jq

test-services-list-ivcap:
	TOKEN=$(shell ivcap --context gke-dev context get access-token --refresh-token); \
	curl \
	-H "content-type: application/json" \
	-H "Timeout: 20" \
	-H "Authorization: Bearer $$TOKEN" \
	https://develop.ivcap.net/1/services2 | jq

install:
	pip install -r requirements.txt

docker-run: DOCKER_TAG=${DOCKER_NAME}_${TARGET_ARCH}:${DOCKER_VERSION}
docker-run: #docker-build
	docker run -it \
		-p ${PORT}:${PORT} \
		--user ${DOCKER_USER} \
		-e LITELLM_PROXY=http://192.168.68.104:4000 \
		--add-host="ivcap.minikube:192.168.68.104" \
		--platform=${TARGET_PLATFORM} \
		--rm \
		${DOCKER_TAG} --port ${PORT}

docker-debug: DOCKER_TAG=${DOCKER_NAME}_${TARGET_ARCH}:${DOCKER_VERSION}
docker-debug: #docker-build
	docker run -it \
		-p ${PORT}:${PORT} \
		--user ${DOCKER_USER} \
		--add-host="ivcap.minikube:192.168.68.104" \
		--platform=${TARGET_PLATFORM} \
		--entrypoint bash \
		${DOCKER_TAG}
