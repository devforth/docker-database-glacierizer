#!/bin/bash

docker build src/ -t devforth/docker-database-glacierizer:latest
docker push devforth/docker-database-glacierizer:latest