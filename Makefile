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

# test-echo:
# 	curl -i -X POST -H "content-type: application/json" --data "{\"echo\": \"Hello World!\"}" http://${HOST}:${PORT}/

# test-echo-with-sleep:
# 	curl -i -X POST -H "content-type: application/json" --data "{\"echo\": \"Hello World!\", \"sleep\":5}" http://${HOST}:${PORT}

# test-echo-with-auth:
# 	curl -i -X POST \
# 		-H "content-type: application/json" \
# 		-H "Authorization: Bearer $(shell ivcap context get access-token --refresh-token)" \
# 		--data "{\"echo\": \"Hello World!\"}" http://${HOST}:${PORT}/


test-simple:
	curl -i -X POST \
	-H "content-type: application/json" \
	-H "Timeout: 60" \
	-H "Authorization: Bearer $(shell ivcap context get access-token --refresh-token)" \
	--data @${PROJECT_DIR}/tests/simple_query.json \
	http://${HOST}:${PORT}

test-is-prime:
	curl -i -X POST \
	-H "content-type: application/json" \
	-H "Timeout: 600" \
	-H "Authorization: Bearer $(shell ivcap context get access-token --refresh-token)" \
	--data @${PROJECT_DIR}/tests/is_prime.json \
	http://${HOST}:${PORT}

test-is-prime-minikube:
	curl -i -X POST \
	-H "content-type: application/json" \
	-H "Timeout: 600" \
	-H "Authorization: Bearer $(shell ivcap context get access-token --refresh-token)" \
	--data @${PROJECT_DIR}/tests/is_prime.json \
	http://ivcap.minikube/1/services2/b35153c3-3f66-5ed1-9e33-c46949783575/jobs


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
