#!/bin/bash

docker stack deploy -c docker-compose.yml -c docker-compose.local-overrides.yml -c sizes-gen04/120sph.yaml -c docker-compose.bdba.yml -c docker-compose.rl.yml hub