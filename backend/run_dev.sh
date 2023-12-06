#!/bin/bash
export FLASK_ENV=development
flask run --port 4649 --debug "$@"
