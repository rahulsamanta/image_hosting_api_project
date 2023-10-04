# Image Hosting API

A Django Rest Framework (DRF) project that will allow any user to upload an image in PNG or JPG format and view them.

## Running instructions with Docker (for local development purposes only)

1. Open the '`Dockerfile`' from the project's root directory
2. In line 6, edit the `ENV DJANGO_SECRET_KEY=secret_key` value and enter the Django secret_key
3. Run the shell script in your preferred terminal with command `source run.sh`
4. Check the Docker container name `docker ps`
5. Create the initial Django admin user `docker exec -it image_hosting_api_app_instance python manage.py createsuperuser`
