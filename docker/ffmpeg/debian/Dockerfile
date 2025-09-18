FROM openjdk:17-slim-bullseye
# FROM maven:3.8-openjdk-17-slim

WORKDIR /root
COPY ffmpeg.tar.gz /root

RUN set -eux; \
  cd /root; \
  tar zxf ffmpeg.tar.gz; \
  cd package; \
  ./install; \
  cd /root; \
  rm -rf *; \
  rm -rf /usr/share/man/* \
    /usr/share/doc/* \
    /usr/share/info/* \
    /var/cache/* \
    /tmp/*

CMD ["ffmpeg", "-codecs"]
