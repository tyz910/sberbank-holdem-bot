IMAGE=tyz910/holdem

run:
	docker run --rm -it -v ${CURDIR}/src:/app -w /app -p 8000:8000 ${IMAGE} pypokergui serve /app/poker_conf.yaml --port 8000 --speed moderate

docker-build:
	docker build -t ${IMAGE} . && (docker ps -q -f status=exited | xargs docker rm) && (docker images -qf dangling=true | xargs docker rmi) && docker images

docker-push:
	docker push ${IMAGE}
