ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:3.19
FROM $BUILD_FROM

# Python + build deps (HA base images are Alpine)
RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app/ /app/app/
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
