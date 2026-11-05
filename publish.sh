#!/bin/bash

TAG="${1:-latest}"
ARCH="$2"

# ./publish.sh 1.17      -> devforth/docker-database-glacierizer:1.17      (amd64)
# ./publish.sh 1.17 arm  -> devforth/docker-database-glacierizer:1.17-arm  (arm64)
if [ "$ARCH" = "arm" ]; then
    # On an x86 machine building for ARM needs emulation, install it once:
    #   docker run --privileged --rm tonistiigi/binfmt --install arm64
    docker buildx build . --platform linux/arm64 -t devforth/docker-database-glacierizer:$TAG-arm --push
else
    docker build . -t devforth/docker-database-glacierizer:$TAG
    docker push devforth/docker-database-glacierizer:$TAG
fi
