#!/bin/sh
set -e

# Check if ini file exists, if not copy from dist
if [ ! -f cessda_skgif_api.ini ]; then
    cp cessda_skgif_api.ini.dist cessda_skgif_api.ini
fi

# Start Gunicorn
exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker cessda_skgif_api.main:app
