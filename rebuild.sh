#!/bin/bash

docker stop five-letters-bot
docker rm five-letters-bot
docker build -t five-letters-bot .
docker run -d --name five-letters-bot --env-file .env -v five-letters-logs:/app/logs five-letters-bot
docker ps -a
