FROM debian:bullseye-slim
WORKDIR /root

RUN set -eux; \
  mkdir -p /root/20250902; \
  mkdir -p /root/.config/uv; \
  mkdir -p /usr/lib/x86_64-linux-gnu;

COPY uv.toml /root/.config/uv/
COPY bin/uv /usr/local/bin/
COPY bin/uvx /usr/local/bin/
COPY bin/upx /usr/local/bin/
COPY bin/objcopy /usr/local/bin/
COPY bin/objdump /usr/local/bin/
COPY bin/strip /usr/local/bin/
COPY lib/libbfd-2.35.2-system.so /usr/lib/
COPY lib/libctf.so.0 /usr/lib/x86_64-linux-gnu
COPY lib/libopcodes-2.35.2-system.so /usr/lib/x86_64-linux-gnu
COPY zip/cpython-3.13.7+20250902-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz /root/20250902

RUN set -eux; \
  UV_PYTHON_INSTALL_MIRROR=file:///root /usr/local/bin/uv python install 3.13; \
  rm -rf /root/20250902; \
  echo 'export PATH=/root/.local/bin:$PATH' >> /root/.bashrc
  
CMD ["sleep", "infinity"]
