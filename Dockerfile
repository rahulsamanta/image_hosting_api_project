FROM python:3.9-slim

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV USER=appuser
ENV DJANGO_SECRET_KEY=secret_key

RUN addgroup --system $USER && adduser --system --group $USER

WORKDIR /app
COPY requirements.txt /app/

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn \
    && apt-get autoremove -y && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/

RUN python manage.py makemigrations
RUN python manage.py migrate

# Change the ownership of the /app directory and switch to non-root user
RUN chown -R $USER:$USER /app
USER $USER

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "image_hosting_api.wsgi:application"]