FROM debian:bullseye-slim
WORKDIR /root

RUN set -eux; \
	\
  mkdir -p /root/20250902; \
  mkdir -p /root/.config/uv; \
  mkdir -p /usr/lib/x86_64-linux-gnu;

COPY bin/uv /usr/bin/
COPY bin/uvx /usr/bin/
COPY zip/cpython-3.13.7+20250902-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz /root/20250902
COPY uv.toml /root/.config/uv/
COPY bin/x86_64-linux-gnu-objcopy /usr/bin/
COPY bin/x86_64-linux-gnu-objdump /usr/bin/
COPY lib/libbfd-2.35.2-system.so /usr/lib/
COPY lib/libctf.so.0.0.0 /usr/lib/x86_64-linux-gnu
COPY lib/libopcodes-2.35.2-system.so /usr/lib/x86_64-linux-gnu

ENV UV_PYTHON_INSTALL_MIRROR=file:///root

RUN set -eux; \
	\
  /usr/bin/uv python install 3.13; \
  rm -rf /root/20250902; \
  /bin/ln -s /usr/bin/x86_64-linux-gnu-objcopy /usr/bin/objcopy; \
  /bin/ln -s /usr/bin/x86_64-linux-gnu-objdump /usr/bin/objdump; \
  /bin/ln -s /usr/lib/x86_64-linux-gnu/libctf.so.0.0.0 /usr/lib/x86_64-linux-gnu/libctf.so.0; \
  /usr/bin/objcopy --version; \
  /usr/bin/objdump --version; \
  /usr/bin/uv --version; \
  /usr/bin/uv run python --version

ENV UV_PYTHON_INSTALL_MIRROR=
  
CMD ["sleep", "infinity"]
