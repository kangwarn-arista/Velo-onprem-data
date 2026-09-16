MAIN_SCRIPT := vco_edge_export.py
BINARY_NAME := vco_edge_export
UBUNTU_18_PANDOC_VERSION := 3.1.1
UBUNTU_18_PANDOC_DEB_URL := https://github.com/jgm/pandoc/releases/download/$(UBUNTU_18_PANDOC_VERSION)/pandoc-$(UBUNTU_18_PANDOC_VERSION)-1-amd64.deb
UV ?= $(shell command -v uv 2>/dev/null || \
	for candidate in "$$HOME/.local/bin/uv" "$$HOME/.cargo/bin/uv" \
		/opt/homebrew/bin/uv /usr/local/bin/uv; do \
		[ -x "$$candidate" ] && { printf '%s' "$$candidate"; break; }; \
	done)

ifeq ($(strip $(UV)),)
UV := uv
endif

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

.PHONY: prep pyinstaller nuitka clean stamp-version bundle package

prep:
	@set -eu; \
	OS="$$(uname -s)"; \
	UV_BIN="$$(command -v uv 2>/dev/null || true)"; \
	if [ -z "$$UV_BIN" ]; then \
		for candidate in "$$HOME/.local/bin/uv" "$$HOME/.cargo/bin/uv" \
			/opt/homebrew/bin/uv /usr/local/bin/uv; do \
			[ -x "$$candidate" ] && { UV_BIN="$$candidate"; break; }; \
		done; \
	fi; \
	echo "Preparing build dependencies for $$OS..."; \
	case "$$OS" in \
		Darwin) \
			if ! xcrun --find clang >/dev/null 2>&1; then \
				echo "Xcode Command Line Tools are required; starting the installer..."; \
				xcode-select --install >/dev/null 2>&1 || true; \
				echo "Complete the Xcode Command Line Tools installation, then rerun 'make prep'."; \
				exit 1; \
			fi; \
			BREW_BIN="$$(command -v brew 2>/dev/null || true)"; \
			if [ -z "$$BREW_BIN" ]; then \
				echo "Homebrew not found; installing it..."; \
				/bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; \
				for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do \
					[ -x "$$candidate" ] && { BREW_BIN="$$candidate"; break; }; \
				done; \
			fi; \
			if [ -z "$$BREW_BIN" ]; then \
				echo "ERROR: Homebrew installation could not be located." >&2; \
				exit 1; \
			fi; \
			eval "$$($$BREW_BIN shellenv)"; \
			command -v pandoc >/dev/null 2>&1 || "$$BREW_BIN" install pandoc; \
			if ! command -v pdflatex >/dev/null 2>&1 && \
				[ ! -x /Library/TeX/texbin/pdflatex ]; then \
				"$$BREW_BIN" install --cask basictex; \
			fi; \
			export PATH="/Library/TeX/texbin:$$PATH"; \
			if [ -z "$$UV_BIN" ]; then \
				"$$BREW_BIN" install uv; \
				UV_BIN="$$(command -v uv 2>/dev/null || true)"; \
			fi; \
			;; \
		Linux) \
			if [ ! -r /etc/os-release ]; then \
				echo "ERROR: Cannot identify this Linux distribution." >&2; \
				exit 1; \
			fi; \
			. /etc/os-release; \
			case " $${ID:-} $${ID_LIKE:-} " in \
				*ubuntu*|*debian*) ;; \
				*) echo "ERROR: Only Ubuntu/Debian Linux is supported (found $${ID:-unknown})." >&2; exit 1 ;; \
			esac; \
			if [ "$$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then \
				echo "ERROR: sudo is required to install system packages." >&2; \
				exit 1; \
			fi; \
			run_as_root() { \
				if [ "$$(id -u)" -eq 0 ]; then "$$@"; else sudo "$$@"; fi; \
			}; \
			PACKAGES="build-essential curl patchelf texlive-latex-base \
				texlive-latex-recommended texlive-fonts-recommended zip"; \
			IS_UBUNTU_18=false; \
			if [ "$${ID:-}" = "ubuntu" ] && [ "$${VERSION_ID:-}" = "18.04" ]; then \
				IS_UBUNTU_18=true; \
				if [ "$$(dpkg --print-architecture)" != "amd64" ]; then \
					echo "ERROR: The Ubuntu 18.04 Pandoc package is available only for amd64." >&2; \
					exit 1; \
				fi; \
				PACKAGES="$$PACKAGES wget texlive-generic-extra texlive-latex-extra"; \
			else \
				PACKAGES="$$PACKAGES pandoc"; \
			fi; \
			MISSING=""; \
			for package in $$PACKAGES; do \
				STATUS="$$(dpkg-query -W -f='$${Status}' "$$package" 2>/dev/null || true)"; \
				[ "$$STATUS" = "install ok installed" ] || MISSING="$$MISSING $$package"; \
			done; \
			if [ -n "$$MISSING" ]; then \
				echo "Installing Ubuntu packages:$$MISSING"; \
				run_as_root apt-get update; \
				run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y $$MISSING; \
			fi; \
			if [ "$$IS_UBUNTU_18" = "true" ]; then \
				INSTALLED_PANDOC_VERSION="$$(pandoc --version 2>/dev/null | sed -n '1s/^pandoc //p')"; \
				if [ -z "$$INSTALLED_PANDOC_VERSION" ] || \
					! dpkg --compare-versions "$$INSTALLED_PANDOC_VERSION" ge "$(UBUNTU_18_PANDOC_VERSION)"; then \
					echo "Installing Pandoc $(UBUNTU_18_PANDOC_VERSION) for Ubuntu 18.04..."; \
					PANDOC_DEB="$$(mktemp /tmp/pandoc-$(UBUNTU_18_PANDOC_VERSION)-XXXXXX)"; \
					if ! wget -q --show-progress -O "$$PANDOC_DEB" "$(UBUNTU_18_PANDOC_DEB_URL)"; then \
						rm -f "$$PANDOC_DEB"; \
						echo "ERROR: Failed to download Pandoc $(UBUNTU_18_PANDOC_VERSION)." >&2; \
						exit 1; \
					fi; \
					run_as_root apt-get purge -y --auto-remove pandoc; \
					if ! run_as_root dpkg -i "$$PANDOC_DEB"; then \
						rm -f "$$PANDOC_DEB"; \
						echo "ERROR: Failed to install Pandoc $(UBUNTU_18_PANDOC_VERSION)." >&2; \
						exit 1; \
					fi; \
					rm -f "$$PANDOC_DEB"; \
				fi; \
			fi; \
			if [ -z "$$UV_BIN" ]; then \
				echo "uv not found; installing it..."; \
				curl -LsSf https://astral.sh/uv/install.sh | sh; \
			fi; \
			;; \
		*) \
			echo "ERROR: Unsupported operating system: $$OS" >&2; \
			exit 1; \
			;; \
	esac; \
	if [ -z "$$UV_BIN" ]; then \
		UV_BIN="$$(command -v uv 2>/dev/null || true)"; \
	fi; \
	if [ -z "$$UV_BIN" ]; then \
		for candidate in "$$HOME/.local/bin/uv" "$$HOME/.cargo/bin/uv" \
			/opt/homebrew/bin/uv /usr/local/bin/uv; do \
			[ -x "$$candidate" ] && { UV_BIN="$$candidate"; break; }; \
		done; \
	fi; \
	if [ -z "$$UV_BIN" ]; then \
		echo "ERROR: uv was installed but could not be located." >&2; \
		exit 1; \
	fi; \
	echo "Synchronizing Python dependencies with $$UV_BIN..."; \
	"$$UV_BIN" sync --all-groups; \
	for command in pandoc pdflatex zip; do \
		command -v "$$command" >/dev/null 2>&1 || \
			{ echo "ERROR: Required command '$$command' is unavailable." >&2; exit 1; }; \
	done; \
	echo "Build environment is ready. Run 'make package', 'make nuitka', or 'make bundle'."

stamp-version:
	@TAG=$$(git describe --tags --abbrev=0 2>/dev/null) && \
	VER=$${TAG#v} && \
	echo "Stamping version: $$VER" && \
	sed -i.bak 's/^__version__ = .*/__version__ = "'"$$VER"'"/' $(MAIN_SCRIPT) && \
	rm -f $(MAIN_SCRIPT).bak

pyinstaller: stamp-version
	$(UV) sync --all-groups
	@$(UV) run python -c "import PyInstaller" 2>/dev/null || \
		{ echo "ERROR: PyInstaller is unavailable. Run 'make prep'."; exit 1; }
	@echo "Detecting imports from $(MAIN_SCRIPT)..."
	@FLAGS=$$($(UV) run python -c "$$DETECT_IMPORTS" $(MAIN_SCRIPT) pyinstaller) && \
	echo "  Flags: $$FLAGS" && \
	$(UV) run python -m PyInstaller \
		--onefile \
		--name $(BINARY_NAME) \
		$$FLAGS \
		$(MAIN_SCRIPT)

nuitka: stamp-version
	$(UV) sync --all-groups
	@$(UV) run python -c "import nuitka" 2>/dev/null || \
		{ echo "ERROR: Nuitka is unavailable. Run 'make prep'."; exit 1; }
	@echo "Detecting imports from $(MAIN_SCRIPT)..."
	@FLAGS=$$($(UV) run python -c "$$DETECT_IMPORTS" $(MAIN_SCRIPT) nuitka) && \
	echo "  Flags: $$FLAGS" && \
	$(UV) run python -m nuitka \
		--standalone \
		--onefile \
		--output-filename=$(BINARY_NAME) \
		--noinclude-pytest-mode=nofollow \
		--noinclude-unittest-mode=nofollow \
		--nofollow-import-to='*.tests' \
		$$FLAGS \
		$(MAIN_SCRIPT)

bundle:
	@test -f $(BINARY_NAME) || \
		{ echo "ERROR: $(BINARY_NAME) not found. Run 'make nuitka' or 'make pyinstaller' first."; exit 1; }
	@command -v pandoc >/dev/null 2>&1 || \
		{ echo "ERROR: pandoc not found. Run 'make prep'."; exit 1; }
	@command -v pdflatex >/dev/null 2>&1 || \
		{ echo "ERROR: pdflatex not found. Run 'make prep'."; exit 1; } && \
	TAG=$$(git describe --tags --abbrev=0 2>/dev/null) && \
	VER=$${TAG#v} && \
	DIR=$(BINARY_NAME)_v$${VER} && \
	echo "Packaging v$${VER} into $${DIR}/" && \
	mkdir -p "$${DIR}" && \
	cp $(BINARY_NAME) "$${DIR}/" && \
	pandoc doc/vco_edge_export_binary.md -o "$${DIR}/vco_edge_export_binary.pdf" \
		--pdf-engine=pdflatex \
		-V geometry:margin=1in \
		-V colorlinks=true && \
	echo "  Created $${DIR}/vco_edge_export_binary.pdf" && \
	zip -r "$${DIR}.zip" "$${DIR}" && \
	echo "Package ready: $${DIR}.zip"

package: clean nuitka bundle

clean:
	rm -rf build/ dist/ *.spec
	rm -rf *.build/ *.dist/ *.onefile-build/
	rm -f $(BINARY_NAME)
	rm -rf $(BINARY_NAME)_v*/
	rm -f $(BINARY_NAME)_v*.zip
