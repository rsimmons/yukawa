#!/bin/bash
export FLASK_ENV=development
flask run --host 0.0.0.0 --port 4649 --debug "$@"
