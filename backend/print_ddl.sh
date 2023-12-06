#!/bin/bash
export FLASK_ENV=development
python -c 'from app import db; db.print_ddl()'
