FROM openjdk:17-slim-bullseye

WORKDIR /root

COPY ffmpeg.tar.gz /root

RUN set -eux; \
	\
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

CMD ["java", "--version"]
