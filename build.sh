#!/bin/bash

TAG="${1:-latest}"

docker build . -t devforth/docker-database-glacierizer:$TAG
