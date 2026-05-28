#!/usr/bin/env bash
set -o errexit

# Install WeasyPrint system dependencies
apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    python3-cffi \
    python3-brotli

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
