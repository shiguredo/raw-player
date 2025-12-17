.PHONY: wheel develop test format clean

sync:
	uv sync


wheel:
	uv build --wheel

develop: sync wheel
	uv pip install -e . --force-reinstall
	@cp _build/cp*/raw_player_ext.pyi src/raw_player/

test: develop
	NO_UV_SYNC=1 uv run pytest --timeout=60

format:
	clang-format -i src/bindings/*.cpp src/bindings/*.h
	uv run ruff format examples/ src/raw_player/

clean:
	rm -rf _build dist *.egg-info _deps
