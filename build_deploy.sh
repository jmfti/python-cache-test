#!/usr/bin/bash

cd images/python 
docker build -f Dockerfile -t python-app-base .
cd ../../
docker network rm app_net
docker network create app_net --attachable -d overlay
# docker stack deploy -c docker-stack.yml prueba
docker stack deploy -c docker-stack.yml tdist-cache && docker service logs -f tdist-cache_app

# docker service logs -f prueba_app
# docker service logs -f prueba_tests-all