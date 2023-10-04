#!/usr/bin/env bash
docker build -t image_hosting_api_app:latest .

docker run --rm image_hosting_api_app:latest sh -c "coverage run --source='.' manage.py test && coverage report -m"

if [ $? -eq 0 ]; then
    echo "All tests passed. Running the app..."
    docker run --name image_hosting_api_app_instance -d -p 8000:8000 image_hosting_api_app:latest
else
    echo "Tests failed."
fi
