MAIN_SCRIPT := vco_edge_export.py
BINARY_NAME := vco_edge_export

# Walks the import tree from MAIN_SCRIPT using ast, follows local .py
# modules recursively, classifies everything as local or third-party,
# and prints the appropriate CLI flags for the requested build tool.
define DETECT_IMPORTS
import ast, sys, os

def get_imports(filepath):
    with open(filepath) as f:
        tree = ast.parse(f.read())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports

stdlib = set(sys.stdlib_module_names)
visited, to_visit = set(), [sys.argv[1]]
local_mods, third_party = set(), set()

while to_visit:
    fp = to_visit.pop()
    if fp in visited:
        continue
    visited.add(fp)
    for name in get_imports(fp):
        if os.path.isfile(name + '.py'):
            if name not in local_mods:
                local_mods.add(name)
                to_visit.append(name + '.py')
        elif name not in stdlib:
            third_party.add(name)

tool = sys.argv[2]
parts = []
if tool == 'pyinstaller':
    for m in sorted(local_mods | third_party):
        parts.append('--hidden-import=' + m)
elif tool == 'nuitka':
    for m in sorted(local_mods):
        parts.append('--include-module=' + m)
    for p in sorted(third_party):
        parts.append('--include-package=' + p)
print(' '.join(parts))
endef
export DETECT_IMPORTS

.PHONY: pyinstaller nuitka clean

pyinstaller:
	uv sync
	@uv run python -c "import PyInstaller" 2>/dev/null || uv add --dev pyinstaller
	@echo "Detecting imports from $(MAIN_SCRIPT)..."
	@FLAGS=$$(uv run python -c "$$DETECT_IMPORTS" $(MAIN_SCRIPT) pyinstaller) && \
	echo "  Flags: $$FLAGS" && \
	uv run python -m PyInstaller \
		--onefile \
		--name $(BINARY_NAME) \
		$$FLAGS \
		$(MAIN_SCRIPT)

nuitka:
	uv sync
	@uv run python -c "import nuitka" 2>/dev/null || uv add --dev nuitka
	@echo "Detecting imports from $(MAIN_SCRIPT)..."
	@FLAGS=$$(uv run python -c "$$DETECT_IMPORTS" $(MAIN_SCRIPT) nuitka) && \
	echo "  Flags: $$FLAGS" && \
	uv run python -m nuitka \
		--standalone \
		--onefile \
		--output-filename=$(BINARY_NAME) \
		$$FLAGS \
		$(MAIN_SCRIPT)

clean:
	rm -rf build/ dist/ *.spec
	rm -rf *.build/ *.dist/ *.onefile-build/
