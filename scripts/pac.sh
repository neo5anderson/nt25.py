#!env bash

# --hidden-import=matplotlib \
# --hidden-import=openpyxl \
# --hidden-import=pandas \
# --hidden-import=scikit-learn \
# --hidden-import=sympy \

src=./src/nt25/lib/et.py

rm -rf dist/*
uv run pyinstaller -F $src &
# uv run pyinstaller --clean -F $src &

docker exec uv rm /root/et.py
docker cp $src uv:/root/
docker exec uv uv run pyinstaller -F et.py
# docker exec uv uv run pyinstaller --clean -F et.py
docker cp uv:/root/dist/et dist

7z a dist-.zip dist
7z l dist-.zip
