# Image Hosting API

A Django Rest Framework (DRF) project that will allow any user to upload an image in PNG or JPG format and view them.

## Running instructions with Docker

1. Open the '`Dockerfile`' from the project's root directory
2. In line 6, edit the `ENV DJANGO_SECRET_KEY=secret_key` value and enter the Django secret_key
3. Build the container `docker build -t image_hosting_api_app .`
4. Run the container `docker run -p 8000:8000 image_hosting_api_app`
5. Check the Docker container name `docker ps`
6. Create the initial Django admin user `docker exec -it <container_name> python manage.py createsuperuser`
