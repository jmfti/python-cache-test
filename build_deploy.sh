#!/usr/bin/bash

cd images/python 
docker build -f Dockerfile -t python-app-base .
docker build -f Locust_Dockerfile -t locust-with-pandas .
cd ../../
cd src/app 
rm -r .pytest_cache
rm -r __pycache__
rm -r routers/__pycache__
cd ../../
docker network rm app_net
docker network create app_net --attachable -d overlay
# docker stack deploy -c docker-stack.yml prueba
docker stack deploy -c docker-stack.yml pruebaPython && docker service logs -f pruebaPython_loadtests-worker #pruebaPython_app #pruebaPython_loadtests-master

# docker service logs -f prueba_app
# docker service logs -f prueba_tests-all