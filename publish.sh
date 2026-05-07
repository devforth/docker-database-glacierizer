#!/bin/bash

#TAG="${1:-latest}"
TAG=sqlite

docker build . -t devforth/docker-database-glacierizer:$TAG
docker push devforth/docker-database-glacierizer:$TAG