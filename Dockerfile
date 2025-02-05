#
FROM python:3.12


WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir -r /code/requirements.txt

RUN apt-get update && apt-get install -y cron
# create cron file
RUN touch /etc/cron.d/updater-cron
RUN echo "0 2 * * * root /bin/bash /code/app/nightly.sh >> /var/log/updater-cron.log 2>&1" >> /etc/cron.d/updater-cron
RUN chmod 0644 /etc/cron.d/updater-cron
RUN touch /var/log/updater-cron.log && chmod 0644 /var/log/updater-cron.log
# Apply cron job
RUN crontab /etc/cron.d/updater-cron

# run with --build-arg FILENAME=... to set the filename
ARG FILENAME=./app/.env
COPY $FILENAME /code/app/.env

COPY ./app/src/ /code/app
RUN chmod 0644 -R /code/app

WORKDIR /code/app
# set UVICORN_WORKERS in env file / deployment definitions.
# example value: "--workers 2"
CMD /etc/init.d/cron start && uvicorn main:app $UVICORN_WORKERS --host 0.0.0.0 --port 5000
