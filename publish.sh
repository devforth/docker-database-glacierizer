#!/bin/bash

docker build src/ -t devforth/docker-database-glacierizer:clean-up-old-dumps
docker push devforth/docker-database-glacierizer:clean-up-old-dumps
