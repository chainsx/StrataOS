SHELL := /bin/bash
PYTHON ?= python3
O ?= $(CURDIR)/output
CONFIG ?= $(CURDIR)/.config
RESUME ?= 1

# Top-level stages share output trees and are deliberately serialized.
# The -j value supplied to this make is inherited by the Python orchestrator
# and used inside package, toolchain, kernel and SquashFS compilation.
.NOTPARALLEL:

.PHONY: all help x86_64_defconfig arm64_defconfig olddefconfig \
        arch-info disk-plan source-lock source-probe toolchain packages kernel \
        components initramfs image check audit preflight verify-config verify-components \
        verify-packages qemu clean distclean dist

all: image

help:
	@printf '%s\n' \
	  'StrataOS native modular OpenRC distribution build' \
	  '' \
	  '  make x86_64_defconfig   Select native x86_64 build' \
	  '  make arm64_defconfig    Select native arm64 build' \
	  '  make -j$$(nproc)          Build with all available CPU threads' \
	  '  make                    Build with the configured/automatic job count' \
	  '  make packages           Build the StrataOS-owned package dependency graph' \
	  '  make check              Run configuration, recipe and unit checks' \
	  '  make audit              Audit all declared build parameters offline' \
	  '  make preflight          Download package sources and verify source options' \
	  '  make qemu               Boot a copy-on-write image in QEMU' \
	  '  make source-probe       Verify all selected source URLs before compiling' \
	  '  make source-lock        Download inputs and record SHA-256 values' \
	  '  make dist               Create a reproducible source archive' \
	  '  make clean              Remove output except the download cache' \
	  '' \
	  'No external distribution build tree or package database is consumed.' \
	  'Override output directory with O=/path/to/output.'

x86_64_defconfig:
	@cp defconfigs/x86_64_defconfig $(CONFIG)
	@echo 'Wrote $(CONFIG)'

arm64_defconfig:
	@cp defconfigs/arm64_defconfig $(CONFIG)
	@echo 'Wrote $(CONFIG)'

olddefconfig:
	@$(PYTHON) scripts/config.py normalize --config $(CONFIG)

arch-info:
	@arch="$$(awk -F= '$$1 == "STRATA_ARCH" {print $$2; exit}' $(CONFIG))"; \
	  test -n "$$arch"; \
	  printf '%s kernel=%s\n' "$$arch" "configs/kernel/$$arch/kernel.config"

disk-plan:
	@./scripts/disk-plan.sh

source-lock:
	@$(PYTHON) scripts/fetch.py --update-lock

source-probe:
	@arch="$$(awk -F= '$$1 == "STRATA_ARCH" {print $$2; exit}' $(CONFIG))"; \
	  test -n "$$arch"; \
	  $(PYTHON) scripts/fetch.py --probe --arch "$$arch" --dl $(O)/dl

toolchain: preflight
	@$(PYTHON) scripts/build.py --config $(CONFIG) --output $(O) toolchain

packages: toolchain
	@$(PYTHON) scripts/build.py --config $(CONFIG) --output $(O) \
	  $(if $(filter 1 yes true,$(RESUME)),--resume,) packages

kernel: toolchain
	@$(PYTHON) scripts/build.py --config $(CONFIG) --output $(O) kernel

components: packages kernel
	@$(PYTHON) scripts/build.py --config $(CONFIG) --output $(O) components

initramfs: packages
	@$(PYTHON) scripts/build.py --config $(CONFIG) --output $(O) initramfs

image: packages kernel components initramfs
	@$(PYTHON) scripts/build.py --config $(CONFIG) --output $(O) image


audit:
	@$(PYTHON) scripts/recipe_audit.py --config $(CONFIG) --output $(O)

preflight: source-probe
	@$(PYTHON) scripts/recipe_audit.py --config $(CONFIG) --output $(O) --fetch

verify-config:
	@./scripts/verify-config.sh

verify-components:
	@./scripts/validate-components.sh

verify-packages:
	@$(PYTHON) scripts/check.py --config $(CONFIG) --output $(O) --packages-only

check: verify-config verify-components audit
	@$(PYTHON) scripts/check.py --config $(CONFIG) --output $(O)
	@$(PYTHON) -m unittest discover -s tests -v

qemu:
	@$(PYTHON) scripts/qemu.py --config $(CONFIG) --output $(O)

clean:
	@$(PYTHON) scripts/build.py --config $(CONFIG) --output $(O) clean

distclean:
	@rm -rf $(O) $(CONFIG)

dist: check
	@./scripts/make-dist.sh
