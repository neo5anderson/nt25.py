FROM maven:3-openjdk-18
WORKDIR /root

RUN set -eux; \
	\
  microdnf install -y --setopt=install_weak_deps=0 oracle-epel-release-el8; \
  dnf install -y --setopt=install_weak_deps=0 https://download1.rpmfusion.org/free/el/rpmfusion-free-release-8.noarch.rpm; \
  dnf install -y --setopt=install_weak_deps=0 https://download1.rpmfusion.org/nonfree/el/rpmfusion-nonfree-release-8.noarch.rpm; \
  dnf config-manager --set-enabled ol8_codeready_builder; \
  dnf install -y --setopt=install_weak_deps=0 ffmpeg ffmpeg-devel; \
  microdnf clean all; \
  rm -rf /usr/share/man/* \
    /usr/share/doc/* \
    /usr/share/info/* \
    /var/cache/* \
    /tmp/*

CMD ["mvn", "-v"]
