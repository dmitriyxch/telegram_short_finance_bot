FROM python:3.7-alpine
RUN apk add --no-cache gcc musl-dev
RUN apk update && apk upgrade && \
    apk add git alpine-sdk bash python3
COPY src/ /usr/local/src
WORKDIR /usr/local/src
RUN mkdir -p /usr/local/src/sessions
RUN pip3 install -r requirements.txt

#run cron for price alerts
RUN echo "*/2 * * * * cd /usr/local/src && bash -c 'python3 notificator.py'" > /etc/crontabs/root

#run main bot app and event looper for alerts
COPY start.sh /
RUN chmod +x /start.sh
ENTRYPOINT ["sh","/start.sh"]