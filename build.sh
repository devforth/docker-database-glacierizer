#!/bin/bash

TAG="${1:-latest}"

docker build src/ -t devforth/docker-database-glacierizer:$TAG