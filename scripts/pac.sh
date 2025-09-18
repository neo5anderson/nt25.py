#!env bash

# --hidden-import=matplotlib \
# --hidden-import=openpyxl \
# --hidden-import=pandas \
# --hidden-import=scikit-learn \
# --hidden-import=sympy \

src=./src/nt25/lib/ef.py

rm -rf dist*

uv run pyinstaller -F $src &
# uv run pyinstaller --clean -F $src &

docker cp $src uv:/root/ && docker exec uv uv run pyinstaller ef.spec && docker cp uv:/root/dist/ef dist

7z a dist-.zip dist
7z l dist-.zip
