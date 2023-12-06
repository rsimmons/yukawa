#!/bin/bash
set -e

#### build deployment artifact for Elastic Beanstalk

# remove old build
rm -f build.zip

# start zip
zip build.zip requirements.txt

# add dirs to zip, using find to get recursion
find app -name __pycache__ -prune -o -print | zip build.zip -@
find .ebextensions | zip build.zip -@
