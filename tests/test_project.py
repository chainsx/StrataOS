from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bootstrap_toolchain import (
    _runtime_candidate_score,
    check_cmake_unused_variables,
    install_compiler_rt_target_runtime,
    libc_defines_symbol,
    missing_cxx_runtime_libraries,
    verify_libcxx_musl_configuration,
    verify_libcxx_musl_library_policy,
    verify_libcxxabi_tls_atexit_configuration,
    verify_runtime_compile_plan,
    verify_runtime_cmake_variable_references,
    verify_runtime_driver_plan,
    verify_runtime_link_plan,
    verify_target_libcxx_installation,
    write_wrapper,
)
from common import (
    BuildError, _archive_compression, _makeflags_without_parallelism,
    _parallel_decompressor, extract, jobs, run, sha256_file,
)
from components import (
    metadata_for_tree, prefer_complete_commands, runtime_path,
    verify_no_build_wrappers,
    write_component_versions,
    write_metadata_pseudo,
)
from config import load, load_data, validate
from fetch import inventory_entries, probe_source
from image import extlinux_config, kernel_command_line, limine_config, write_gpt_image
from initramfs import validate_util_linux_tools, write_newc
from package_builder import (
    HOST_RECIPES, PackageBuilder, Recipe, apply_kconfig_fragment, component_package_names,
    has_llvm_runtime_libraries, load_recipes, read_kconfig_values, topological_order,
    verify_kconfig_fragment,
)
from recipe_audit import (
    SPECIAL_CONTRACTS, _cmake_options, _meson_options, audit_source_recipes,
    audit_static_recipes,
)
from build_policy import (
    RUNTIME_C_COMPILE_FLAGS, RUNTIME_CXX_COMPILE_FLAGS, RUNTIME_LINK_FLAGS,
    TARGET_CXX_LINK_FLAGS, TARGET_LINK_FLAGS, SANITIZED_ENVIRONMENT,
    target_build_options, target_c_compile_flags, target_cxx_header_flags,
    target_libcxx_include_dir, target_link_flags,
)
from recipes import Source, load_toolchain_inputs
from qemu import prepare_vars, qemu_acceleration_args, qemu_disk_mib
from rootfs import install_base_configuration


class ProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.x86 = load(ROOT / "defconfigs/x86_64_defconfig")
        self.arm = load(ROOT / "defconfigs/arm64_defconfig")

    def test_configs_validate_without_cross_architecture_build(self) -> None:
        validate(self.x86, native=False)
        validate(self.arm, native=False)
        self.assertEqual("x86_64", self.x86["STRATA_ARCH"])
        self.assertEqual("arm64", self.arm["STRATA_ARCH"])

    def test_esp_component_policy_is_complete_and_enforced_at_boot(self) -> None:
        policy = load_data(ROOT / "configs/runtime/components.conf")
        manifests = sorted((ROOT / "components").glob("*/component.conf"))
        self.assertEqual("1", policy["format"])
        self.assertEqual("yes", policy["component.system-core.enabled"])
        self.assertEqual(
            {"format"} | {f"component.{path.parent.name}.enabled" for path in manifests},
            set(policy),
        )
        init = (ROOT / "initramfs/init").read_text()
        runtime = (ROOT / "initramfs/bin/strata-componentd").read_text()
        image = (ROOT / "scripts/image.py").read_text()
        self.assertIn('"$CONFIG_DIR/components.conf"', init)
        self.assertIn('COMPONENTS_CONF="$CONFIG/components.conf"', runtime)
        self.assertIn('component $name disabled by ESP policy', runtime)
        self.assertIn('"components.conf": ROOT / "configs/runtime/components.conf"', image)

    def test_target_build_policies_are_arch_specific_and_portable(self) -> None:
        for arch in ("x86_64", "arm64"):
            options = target_build_options(arch)
            self.assertEqual("thin", options["lto"])
            self.assertEqual("yes", options["section_gc"])
            self.assertEqual("", options["cpu_flags"])
            self.assertIn("-flto=thin", target_c_compile_flags(arch))
            self.assertIn("-flto=thin", target_link_flags(arch))
            self.assertIn("-Wl,--gc-sections", target_link_flags(arch))

    def test_package_layout_is_owned_by_package_directories(self) -> None:
        recipes = load_recipes()
        self.assertIn("linux", recipes)
        self.assertEqual("kernel", recipes["linux"].build_system)
        self.assertFalse(any((ROOT / "packages").glob("*.toml")))
        self.assertFalse((ROOT / "patches").exists())
        self.assertFalse((ROOT / "package-configs").exists())
        for name, recipe in recipes.items():
            self.assertEqual(ROOT / "packages" / name / f"{name}.toml", recipe.path)

    def test_defconfigs_do_not_control_package_versions(self) -> None:
        for config in (self.x86, self.arm):
            for key in (
                "STRATA_LINUX_VERSION", "STRATA_DOCKER_VERSION",
            ):
                self.assertNotIn(key, config)

    def test_bootloader_selection_requires_one_supported_mode(self) -> None:
        self.assertEqual("limine-efi", self.x86["STRATA_BOOTLOADER"])
        self.assertEqual("limine-efi", self.arm["STRATA_BOOTLOADER"])
        extlinux = dict(self.x86)
        extlinux["STRATA_BOOTLOADER"] = "extlinux"
        extlinux.pop("STRATA_LIMINE_VERSION")
        validate(extlinux, native=False)
        invalid = dict(self.x86, STRATA_BOOTLOADER="grub-efi")
        with self.assertRaisesRegex(BuildError, "limine-efi or extlinux"):
            validate(invalid, native=False)

    def test_clang_wrapper_supports_autoconf_probes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            llvm = tmp / "llvm"
            llvm.mkdir()
            sysroot = tmp / "sysroot"
            (sysroot / "usr/lib").mkdir(parents=True)
            (sysroot / "usr/lib/libc.a").write_text("musl")
            clang = llvm / "clang"
            clang.write_text("#!/bin/sh\nprintf 'delegated:%s\\n' \"$*\"\n")
            clang.chmod(0o755)
            (llvm / "ld.lld").write_text("")
            wrapper = tmp / "x86_64-linux-musl-gcc"
            write_wrapper(wrapper, "x86_64-linux-musl", llvm, sysroot)
            self.assertEqual(
                "x86_64-linux-musl",
                subprocess.check_output([wrapper, "-dumpmachine"], text=True).strip(),
            )
            self.assertEqual(
                str(sysroot / "usr/lib/libc.a"),
                subprocess.check_output([wrapper, "-print-file-name=libc.a"], text=True).strip(),
            )

    def test_cxx_wrapper_forces_target_libcxx_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            llvm = tmp / "llvm"
            llvm.mkdir()
            sysroot = tmp / "sysroot"
            include = target_libcxx_include_dir(sysroot)
            include.mkdir(parents=True)
            (include / "__config_site").write_text("#define _LIBCPP_HAS_MUSL_LIBC\n")
            clang = llvm / "clang++"
            clang.write_text("#!/bin/sh\nprintf '%s\n' \"$*\"\n")
            clang.chmod(0o755)
            (llvm / "ld.lld").write_text("")
            wrapper = tmp / "x86_64-linux-musl-c++"
            write_wrapper(wrapper, "x86_64-linux-musl", llvm, sysroot, cxx=True)
            delegated = subprocess.check_output([wrapper, "-c", "probe.cpp"], text=True)
            self.assertIn("-nostdinc++", delegated)
            self.assertIn(str(include), delegated)
            self.assertNotIn("-stdlib=libc++", delegated)
            self.assertNotIn("-fuse-ld=lld", delegated)
            linked = subprocess.check_output([wrapper, "probe.cpp", "-o", "probe"], text=True)
            self.assertIn("-stdlib=libc++", linked)
            self.assertIn("--unwindlib=libunwind", linked)
            self.assertIn("-fuse-ld=lld", linked)

    def test_target_libcxx_installation_requires_generated_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            sysroot = Path(tmp_name) / "sysroot"
            include = target_libcxx_include_dir(sysroot)
            include.mkdir(parents=True)
            for name in ("__config", "__config_site", "cstddef", "locale"):
                (include / name).write_text(name)
            self.assertEqual(include, verify_target_libcxx_installation(sysroot))
            (include / "__config_site").unlink()
            with self.assertRaisesRegex(RuntimeError, "__config_site"):
                verify_target_libcxx_installation(sysroot)

    def test_target_cxx_header_flags_disable_native_header_discovery(self) -> None:
        sysroot = Path("/target/sysroot")
        flags = target_cxx_header_flags(sysroot)
        self.assertEqual("-nostdinc++", flags[0])
        self.assertEqual("-isystem", flags[1])
        self.assertEqual(str(sysroot / "usr/include/c++/v1"), flags[2])

    def test_target_cxx_header_policy_is_wired_into_all_build_systems(self) -> None:
        builder = (ROOT / "scripts/package_builder.py").read_text()
        bootstrap = (ROOT / "scripts/bootstrap_toolchain.py").read_text()
        self.assertGreaterEqual(builder.count("target_cxx_header_flags"), 3)
        self.assertIn('-nostdinc++ -isystem "$SYSROOT/usr/include/c++/v1"', bootstrap)
        self.assertIn("*target_cxx_header_flags(sysroot)", bootstrap)

    def test_parallel_jobs_inherit_top_level_makeflags(self) -> None:
        self.assertEqual(7, jobs(0, " -j7 --jobserver-auth=fifo:/tmp/jobs"))
        self.assertEqual(5, jobs(0, "--jobs=5"))
        self.assertEqual(3, jobs(3, "-j12"))

    def test_parallel_archive_decompressors_use_requested_jobs(self) -> None:
        self.assertEqual("xz", _archive_compression(Path("LLVM.tar.xz")))
        self.assertEqual("gzip", _archive_compression(Path("cmake.tgz")))
        with patch("common.shutil.which", side_effect=lambda name: f"/usr/bin/{name}"):
            xz, xz_parallel = _parallel_decompressor(Path("LLVM.tar.xz"), 12)
            gzip, gzip_parallel = _parallel_decompressor(Path("cmake.tar.gz"), 12)
        self.assertEqual(["/usr/bin/xz", "-dc", "-T12"], xz)
        self.assertTrue(xz_parallel)
        self.assertEqual(["/usr/bin/pigz", "-dc", "-p", "12"], gzip)
        self.assertTrue(gzip_parallel)

    def test_parallel_toolchain_extraction_is_wired_to_build_jobs(self) -> None:
        source = (ROOT / "scripts/bootstrap_toolchain.py").read_text()
        self.assertGreaterEqual(source.count("parallelism=j"), 5)
        build = (ROOT / "scripts/build.py").read_text()
        self.assertIn('commands.append("pigz")', build)

    def test_parallel_xz_extraction_integration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source/top/sub"
            source.mkdir(parents=True)
            (source / "file.txt").write_text("parallel extraction\n")
            archive = tmp / "sample.tar.xz"
            subprocess.run(
                ["tar", "-cJf", str(archive), "top"],
                cwd=tmp / "source", check=True,
            )
            destination = extract(archive, tmp / "destination", parallelism=2)
            self.assertEqual(
                "parallel extraction",
                (destination / "sub/file.txt").read_text().strip(),
            )

    def test_extract_collapses_archive_root_after_leading_dot_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            package = tmp / "source/AppStream-1.0.4"
            package.mkdir(parents=True)
            (package / "meson.build").write_text("project('appstream')\n")
            archive = tmp / "AppStream-1.0.4.tar.xz"
            subprocess.run(
                ["tar", "-cJf", str(archive), "./AppStream-1.0.4"],
                cwd=tmp / "source", check=True,
            )
            destination = extract(archive, tmp / "appstream", parallelism=2)
            self.assertTrue((destination / "meson.build").is_file())
            self.assertFalse((destination / "AppStream-1.0.4").exists())

    def test_extract_preserves_unrelated_single_directory_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            payload = tmp / "source/top/data"
            payload.mkdir(parents=True)
            (payload / "file.txt").write_text("payload\n")
            archive = tmp / "sample.tar.xz"
            subprocess.run(
                ["tar", "-cJf", str(archive), "top"],
                cwd=tmp / "source", check=True,
            )
            destination = extract(archive, tmp / "destination", parallelism=2)
            self.assertEqual("payload", (destination / "data/file.txt").read_text().strip())

    def test_extract_allows_inert_absolute_symlink_in_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source/top/tests/samples"
            source.mkdir(parents=True)
            missing = Path(f"/strataos-definitely-missing-{uuid.uuid4().hex}")
            (source / "bad-link.xml").symlink_to(missing)
            archive = tmp / "fixture.tar.xz"
            subprocess.run(["tar", "-cJf", str(archive), "top"], cwd=tmp / "source", check=True)
            destination = extract(archive, tmp / "destination", parallelism=2)
            link = destination / "tests/samples/bad-link.xml"
            self.assertTrue(link.is_symlink())
            self.assertEqual(str(missing), os.readlink(link))

    def test_extract_rejects_external_symlink_outside_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source/top/bin"
            source.mkdir(parents=True)
            external = tmp / "host-secret"
            external.write_text("secret")
            (source / "escape").symlink_to(external)
            archive = tmp / "escape.tar.xz"
            subprocess.run(["tar", "-cJf", str(archive), "top"], cwd=tmp / "source", check=True)
            with self.assertRaises(BuildError):
                extract(archive, tmp / "destination", parallelism=2)

    def test_extract_rejects_fixture_symlink_to_existing_host_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source/top/tests/fixtures"
            source.mkdir(parents=True)
            external = tmp / "existing-host-file"
            external.write_text("host")
            (source / "bad-link").symlink_to(external)
            archive = tmp / "fixture-escape.tar.xz"
            subprocess.run(["tar", "-cJf", str(archive), "top"], cwd=tmp / "source", check=True)
            with self.assertRaises(BuildError):
                extract(archive, tmp / "destination", parallelism=2)

    def test_extract_rejects_missing_fixture_target_below_existing_host_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source/top/tests/fixtures"
            source.mkdir(parents=True)
            external = tmp / "not-created"
            (source / "bad-link").symlink_to(external)
            archive = tmp / "fixture-writable-host.tar.xz"
            subprocess.run(["tar", "-cJf", str(archive), "top"], cwd=tmp / "source", check=True)
            with self.assertRaises(BuildError):
                extract(archive, tmp / "destination", parallelism=2)

    def test_compiler_rt_runtime_is_materialized_for_musl_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            llvm = tmp / "llvm"
            llvm_bin = llvm / "bin"
            llvm_bin.mkdir(parents=True)
            source_dir = llvm / "lib/clang/22/lib/x86_64-unknown-linux-gnu"
            source_dir.mkdir(parents=True)
            (source_dir / "libclang_rt.builtins.a").write_text("archive")
            (source_dir / "clang_rt.crtbegin.o").write_text("crt")
            expected = llvm / "lib/clang/22/lib/x86_64-unknown-linux-musl/libclang_rt.builtins.a"
            clang = llvm_bin / "clang"
            clang.write_text(
                "#!/bin/sh\n"
                f"printf '%s\n' '{expected}'\n"
            )
            clang.chmod(0o755)
            nm = llvm_bin / "llvm-nm"
            nm.write_text(
                "#!/bin/sh\n"
                "printf '%s\n' '__muldc3' '__mulsc3' '__mulxc3'\n"
            )
            nm.chmod(0o755)
            result = install_compiler_rt_target_runtime(
                llvm, llvm_bin, "x86_64-linux-musl", "x86_64"
            )
            self.assertEqual(expected, result)
            self.assertEqual("archive", expected.read_text())
            self.assertTrue((expected.parent / "clang_rt.crtbegin.o").exists())

    def test_cxx_runtime_cache_requires_libcxx_and_unwind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name) / "sysroot"
            library_dir = root / "usr/lib"
            library_dir.mkdir(parents=True)
            self.assertEqual(
                ("libc++.so.1", "libunwind.so.1"),
                missing_cxx_runtime_libraries(root),
            )
            (library_dir / "libc++.so.1").write_text("libc++")
            self.assertEqual(("libunwind.so.1",), missing_cxx_runtime_libraries(root))
            (library_dir / "libunwind.so.1").write_text("unwind")
            self.assertEqual((), missing_cxx_runtime_libraries(root))
            self.assertTrue(has_llvm_runtime_libraries(root))
            (library_dir / "libunwind.so.1").unlink()
            self.assertFalse(has_llvm_runtime_libraries(root))

    def test_libcxx_musl_configuration_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            site = tmp / "include/c++/v1/__config_site"
            site.parent.mkdir(parents=True)
            site.write_text("#define _LIBCPP_HAS_MUSL_LIBC\n")
            self.assertEqual(site, verify_libcxx_musl_configuration(tmp))
            site.write_text("/* musl support missing */\n")
            with self.assertRaisesRegex(RuntimeError, "not configured for musl"):
                verify_libcxx_musl_configuration(tmp)

    def test_runtime_configuration_enables_musl_libcxx(self) -> None:
        source = (ROOT / "scripts/bootstrap_toolchain.py").read_text()
        self.assertIn('"-DLIBCXX_HAS_MUSL_LIBC=ON"', source)
        self.assertIn("verify_libcxx_musl_configuration(runtimes_build)", source)
        self.assertIn("smoke_test_libcxx_link", source)
        self.assertIn("verify_target_libcxx_installation", source)
        self.assertIn("-nostdinc++", source)

    def test_runtime_compile_and_link_flags_are_separated(self) -> None:
        for token in ("-fuse-ld=lld", "--rtlib=compiler-rt", "--unwindlib=none"):
            self.assertNotIn(token, RUNTIME_C_COMPILE_FLAGS)
            self.assertNotIn(token, RUNTIME_CXX_COMPILE_FLAGS)
            self.assertIn(token, RUNTIME_LINK_FLAGS)

    def test_runtime_compile_plan_rejects_link_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flags = tmp / "libcxx/CMakeFiles/cxx.dir/flags.make"
            flags.parent.mkdir(parents=True)
            flags.write_text("CXX_FLAGS = -O2 -fPIC\n")
            verify_runtime_compile_plan(tmp)
            flags.write_text("CXX_FLAGS = -O2 -fuse-ld=lld --rtlib=compiler-rt\n")
            with self.assertRaisesRegex(RuntimeError, "link-only flags"):
                verify_runtime_compile_plan(tmp)

    def test_cmake_unused_runtime_variables_are_fatal(self) -> None:
        check_cmake_unused_variables("-- Configuring done\n", "runtime")
        output = (
            "CMake Warning:\n  Manually-specified variables were not used by the project:\n\n"
            "    LIBCXX_HAS_GCC_LIB\n\n-- Build files have been written\n"
        )
        with self.assertRaisesRegex(RuntimeError, "LIBCXX_HAS_GCC_LIB"):
            check_cmake_unused_variables(output, "runtime")

    def test_runtime_options_must_exist_in_selected_llvm_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            cmake = tmp / "libcxx/CMakeLists.txt"
            cmake.parent.mkdir(parents=True)
            cmake.write_text("option(LIBCXX_HAS_MUSL_LIBC \"musl\" OFF)\n")
            verify_runtime_cmake_variable_references(
                tmp, ["-DLIBCXX_HAS_MUSL_LIBC=ON"]
            )
            with self.assertRaisesRegex(RuntimeError, "LIBCXX_REMOVED_OPTION"):
                verify_runtime_cmake_variable_references(
                    tmp, ["-DLIBCXX_HAS_MUSL_LIBC=ON", "-DLIBCXX_REMOVED_OPTION=OFF"]
                )

    def test_libcxxabi_tls_atexit_capability_is_forced_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            (tmp / "CMakeCache.txt").write_text(
                "LIBCXXABI_HAS_CXA_THREAD_ATEXIT_IMPL:UNINITIALIZED=OFF\n"
            )
            flags = tmp / "libcxxabi/src/CMakeFiles/cxxabi_shared_objects.dir/flags.make"
            flags.parent.mkdir(parents=True)
            flags.write_text("CXX_DEFINES = -D_LIBCXXABI_BUILDING_LIBRARY\n")
            verify_libcxxabi_tls_atexit_configuration(tmp, False)
            flags.write_text(
                "CXX_DEFINES = -DHAVE___CXA_THREAD_ATEXIT_IMPL\n"
            )
            with self.assertRaisesRegex(RuntimeError, "strong __cxa_thread_atexit_impl"):
                verify_libcxxabi_tls_atexit_configuration(tmp, False)

    def test_libcxx_musl_library_policy_is_forced_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            valid = (
                "LIBCXX_HAS_PTHREAD_API:UNINITIALIZED=ON\n"
                "LIBCXX_HAS_RT_LIB:UNINITIALIZED=OFF\n"
                "LIBCXX_HAS_PTHREAD_LIB:UNINITIALIZED=OFF\n"
                "LIBCXX_HAS_ATOMIC_LIB:UNINITIALIZED=OFF\n"
                "LIBCXXABI_HAS_C_LIB:UNINITIALIZED=ON\n"
                "LIBCXXABI_HAS_PTHREAD_LIB:UNINITIALIZED=OFF\n"
                "LIBUNWIND_HAS_DL_LIB:UNINITIALIZED=OFF\n"
                "LIBUNWIND_HAS_PTHREAD_LIB:UNINITIALIZED=OFF\n"
            )
            (tmp / "CMakeCache.txt").write_text(valid)
            verify_libcxx_musl_library_policy(tmp)
            (tmp / "CMakeCache.txt").write_text(
                valid.replace("LIBUNWIND_HAS_DL_LIB:UNINITIALIZED=OFF",
                              "LIBUNWIND_HAS_DL_LIB:UNINITIALIZED=ON")
            )
            with self.assertRaisesRegex(RuntimeError, "LIBUNWIND_HAS_DL_LIB"):
                verify_libcxx_musl_library_policy(tmp)

    def test_all_cmake_unused_variables_are_fatal(self) -> None:
        recipe = Recipe(
            name="probe", version="1", source=None, kind="target",
            build_system="cmake", dependencies=(), configure_args=(),
            cppflags=(), special=None, path=Path("probe.toml"),
        )
        output = (
            "CMake Warning:\n"
            "  Manually-specified variables were not used by the project:\n\n"
            "    STRATA_GLOBAL_LINK_POLICY\n\n"
            "-- Build files have been written\n"
        )
        with self.assertRaisesRegex(RuntimeError, "STRATA_GLOBAL_LINK_POLICY"):
            PackageBuilder._check_configure_output(recipe, output, "cmake")

    def test_cmake_source_audit_accepts_variables_checked_with_defined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name)
            (source / "CMakeLists.txt").write_text(
                "if(NOT DEFINED LLVM_EXTERNAL_SPIRV_HEADERS_SOURCE_DIR)\n"
                "  message(FATAL_ERROR missing)\n"
                "endif()\n"
            )
            self.assertIn(
                "LLVM_EXTERNAL_SPIRV_HEADERS_SOURCE_DIR", _cmake_options(source)
            )

    def test_host_cmake_does_not_pass_unused_cxx_cache_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source"
            source.mkdir()
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.cmake_bin = tmp / "cmake/bin"
            builder.host = tmp / "host"
            builder.llvm_bin = tmp / "llvm/bin"
            builder.output = tmp / "output"
            builder.parallel = 1
            recipe = Recipe(
                name="host-zlib", version="1.3.1", source="zlib", kind="host",
                build_system="cmake", dependencies=(),
                configure_args=("-DZLIB_BUILD_EXAMPLES=OFF",), cppflags=(),
                special=None, path=tmp / "host-zlib.toml",
            )
            env = {"CC": str(builder.llvm_bin / "clang"), "CXX": str(builder.llvm_bin / "clang++")}
            with patch("package_builder.run", return_value=subprocess.CompletedProcess([], 0, "", "")) as mocked_run, \
                 patch.object(builder, "audit_generated_build_plan"):
                builder.build_cmake(recipe, source, tmp / "build", tmp / "root", env, {})
            configure = mocked_run.call_args_list[0].args[0]
            self.assertNotIn(f"-DCMAKE_CXX_COMPILER={builder.llvm_bin / 'clang++'}", configure)
            self.assertNotIn("-DCMAKE_CXX_FLAGS_INIT=-O2 -pipe -fPIC", configure)
            self.assertIn("-DZLIB_BUILD_EXAMPLES=OFF", configure)

    def test_host_glslang_audits_binary_and_source_archives(self) -> None:
        recipe = load_recipes()["host-glslang"]
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source_archive = tmp / "source-archive"
            source_archive.mkdir()
            (source_archive / "CMakeLists.txt").write_text("project(glslang)\n")
            report = audit_source_recipes(
                {"host-glslang": recipe}, {"host-glslang": source_archive}
            )
            self.assertEqual("source-options-ok", report[0]["source_status"])

            binary_archive = tmp / "binary-archive"
            validator = binary_archive / "bin/glslangValidator"
            validator.parent.mkdir(parents=True)
            validator.write_text("prebuilt validator\n")
            report = audit_source_recipes(
                {"host-glslang": recipe}, {"host-glslang": binary_archive}
            )
            self.assertEqual("source-options-ok", report[0]["source_status"])

    def test_host_glslang_keeps_x86_binary_path_and_builds_arm64_source(self) -> None:
        recipe = load_recipes()["host-glslang"]
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.host = tmp / "host"
            builder.host_bin = builder.host / "bin"
            builder.host_bin.mkdir(parents=True)

            binary_source = tmp / "x86-source"
            validator = binary_source / "bin/glslangValidator"
            validator.parent.mkdir(parents=True)
            validator.write_text("x86 release validator\n")
            builder.arch = "x86_64"
            builder.special_host_glslang(recipe, binary_source, tmp / "x86-build", tmp / "root", {}, {})
            self.assertEqual(
                "x86 release validator\n",
                (builder.host_bin / "glslangValidator").read_text(),
            )

            builder.host = tmp / "arm-host"
            builder.host_bin = builder.host / "bin"
            builder.host_bin.mkdir(parents=True)
            source = tmp / "arm-source"
            source.mkdir()
            (source / "CMakeLists.txt").write_text("project(glslang)\n")
            builder.arch = "arm64"
            builder.cmake_bin = tmp / "cmake/bin"
            builder.llvm_bin = tmp / "llvm/bin"
            builder.parallel = 2

            def mock_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                if "--install" in command:
                    installed = builder.host_bin / "glslang"
                    installed.write_text("arm source validator\n")
                    (builder.host_bin / "glslangValidator").symlink_to(installed.name)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("package_builder.run", side_effect=mock_run) as mocked_run:
                builder.special_host_glslang(
                    recipe, source, tmp / "arm-build", tmp / "root", {}, {}
                )

            configure = mocked_run.call_args_list[0].args[0]
            self.assertIn("-DBUILD_EXTERNAL=OFF", configure)
            self.assertIn("-DENABLE_OPT=OFF", configure)
            self.assertIn("-DGLSLANG_TESTS=OFF", configure)
            self.assertIn(f"-DCMAKE_CXX_COMPILER={builder.llvm_bin / 'clang++'}", configure)
            self.assertTrue((builder.host_bin / "glslangValidator").is_file())

    def test_glib_meson_tools_use_host_scripts_and_native_target_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.arch = "arm64"
            builder.output = tmp / "output"
            builder.host_bin = builder.output / "host/bin"
            builder.host_bin.mkdir(parents=True)
            builder.sysroot = builder.output / "toolchain/sysroot"
            target_bin = builder.sysroot / "usr/bin"
            target_bin.mkdir(parents=True)
            (builder.output / "generated").mkdir(parents=True)
            run_target = builder.output / "generated/run-target"
            run_target.write_text("#!/bin/sh\nexit 0\n")

            script = target_bin / "glib-mkenums"
            script.write_text("#!/usr/bin/env python3\nprint('glib-mkenums')\n")
            script.chmod(0o755)
            native_binary = target_bin / "glib-compile-resources"
            native_binary.write_bytes(b"\\x7fELF target binary")
            other_binary = target_bin / "glib-compile-schemas"
            other_binary.write_bytes(b"\\x7fELF target binary")

            with patch("package_builder.platform.machine", return_value="aarch64"):
                builder.prepare_glib_build_tools()

            script_wrapper = (builder.host_bin / "glib-mkenums").read_text()
            self.assertIn(str(builder.host_bin / "python3"), script_wrapper)
            self.assertIn(str(script), script_wrapper)
            wrapper = (builder.host_bin / "glib-compile-resources").read_text()
            self.assertIn(str(run_target), wrapper)
            self.assertIn(str(native_binary), wrapper)
            self.assertTrue(os.access(builder.host_bin / "glib-compile-resources", os.X_OK))
            self.assertTrue(os.access(builder.host_bin / "glib-compile-schemas", os.X_OK))

    def test_target_cmake_does_not_pass_unused_install_libdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source"
            source.mkdir()
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.cmake_bin = tmp / "cmake/bin"
            builder.output = tmp / "output"
            builder.parallel = 1
            recipe = Recipe(
                name="zlib", version="1.3.1", source="zlib", kind="target",
                build_system="cmake", dependencies=(),
                configure_args=("-DZLIB_BUILD_EXAMPLES=OFF",), cppflags=(),
                special=None, path=tmp / "zlib.toml",
            )
            env = {"CC": "/toolchain/cc"}
            with patch("package_builder.run", return_value=subprocess.CompletedProcess([], 0, "", "")) as mocked_run, \
                 patch.object(builder, "audit_generated_build_plan"):
                builder.build_cmake(recipe, source, tmp / "build", tmp / "root", env, {})
            configure = mocked_run.call_args_list[0].args[0]
            self.assertIn(f"-DCMAKE_TOOLCHAIN_FILE={builder.output / 'generated/cmake-toolchain.cmake'}", configure)
            self.assertIn("-DCMAKE_INSTALL_PREFIX=/usr", configure)
            self.assertNotIn("-DCMAKE_INSTALL_LIBDIR=lib", configure)

    def test_zstd_uses_environment_linker_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source"
            source.mkdir()
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.host = tmp / "host"
            builder.parallel = 1
            recipe = replace(load_recipes()["host-zstd"], path=tmp / "host-zstd.toml")
            env = {
                "CC": "/toolchain/clang", "AR": "/toolchain/llvm-ar",
                "RANLIB": "/toolchain/llvm-ranlib", "CFLAGS": "-O2 -fPIC",
                "LDFLAGS": "-fuse-ld=lld",
            }
            with patch("package_builder.run") as mocked_run:
                builder.special_zstd(recipe, source, tmp / "build", tmp / "root", env, {"host": str(builder.host)})
            build_args = mocked_run.call_args_list[0].args[0]
            install_args = mocked_run.call_args_list[1].args[0]
            self.assertNotIn("LDFLAGS=-fuse-ld=lld", build_args)
            self.assertEqual("-fuse-ld=lld", mocked_run.call_args_list[0].kwargs["env"]["LDFLAGS"])
            self.assertIn(f"LIBDIR={builder.host / 'lib'}", install_args)
            self.assertIn(f"INCLUDEDIR={builder.host / 'include'}", install_args)

    def test_target_zstd_installs_metadata_under_usr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source"
            source.mkdir()
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.parallel = 1
            recipe = replace(load_recipes()["zstd"], path=tmp / "zstd.toml")
            env = {
                "CC": "/toolchain/cc", "AR": "/toolchain/ar",
                "RANLIB": "/toolchain/ranlib", "CFLAGS": "-O2 -fPIC",
            }
            with patch("package_builder.run") as mocked_run:
                builder.special_zstd(recipe, source, tmp / "build", tmp / "root", env, {})
            install_args = mocked_run.call_args_list[1].args[0]
            self.assertIn("LIBDIR=/usr/lib", install_args)
            self.assertIn("INCLUDEDIR=/usr/include", install_args)
            self.assertIn(f"DESTDIR={tmp / 'root'}", install_args)



    def test_openssl_uses_absolute_target_compiler_without_cross_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source"
            source.mkdir()
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.arch = "x86_64"
            builder.parallel = 1
            recipe = replace(load_recipes()["openssl"], path=tmp / "openssl.toml")
            env = {"CC": "/toolchain/x86_64-linux-musl-cc"}
            with patch("package_builder.run") as mocked_run:
                builder.special_openssl(recipe, source, tmp / "build", tmp / "root", env, {"openssl_target": "linux-x86_64"})
            configure_args = mocked_run.call_args_list[0].args[0]
            self.assertIn("linux-x86_64", configure_args)
            self.assertIn("--libdir=lib", configure_args)
            self.assertNotIn("--cross-compile-prefix", " ".join(configure_args))
            self.assertIs(env, mocked_run.call_args_list[0].kwargs["env"])

    def test_bzip2_build_skips_target_self_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            source = tmp / "source"
            source.mkdir()
            for name in ("bzip2", "bzip2recover", "bzlib.h", "libbz2.a", "libbz2.so.1.0.8"):
                (source / name).write_text(name)
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.parallel = 1
            recipe = replace(load_recipes()["bzip2"], path=tmp / "bzip2.toml")
            env = {
                "CC": "/toolchain/cc", "AR": "/toolchain/ar",
                "RANLIB": "/toolchain/ranlib", "CFLAGS": "-O2 -fPIC",
                "LDFLAGS": "-fuse-ld=lld",
            }
            with patch("package_builder.run") as mocked_run:
                builder.special_bzip2(recipe, source, tmp / "build", tmp / "root", env, {})
            build_args = mocked_run.call_args_list[1].args[0]
            self.assertEqual(("libbz2.a", "bzip2", "bzip2recover"), tuple(build_args[-3:]))
            self.assertNotIn("test", build_args)

    def test_host_e2fsprogs_silences_clang_shared_compile_warning(self) -> None:
        recipe = load_recipes()["host-e2fsprogs"]
        self.assertEqual(("-Wno-unused-command-line-argument",), recipe.cppflags)
        self.assertEqual(("LDCONFIG=:",), recipe.environment)
        for argument in (
            "--with-udev-rules-dir=no", "--with-crond-dir=no",
            "--with-systemd-unit-dir=no",
        ):
            self.assertIn(argument, recipe.configure_args)

    def test_util_linux_enables_libfdisk_with_fdisk_utilities(self) -> None:
        recipe = load_recipes()["util-linux"]
        self.assertIn("--enable-fdisks", recipe.configure_args)
        self.assertIn("--enable-libfdisk", recipe.configure_args)
        self.assertIn("--enable-libsmartcols", recipe.configure_args)
        self.assertIn("--without-tinfo", recipe.configure_args)
        self.assertIn("--disable-makeinstall-chown", recipe.configure_args)
        self.assertIn("--disable-makeinstall-setuid", recipe.configure_args)
        self.assertEqual(("NCURSESW6_CONFIG=false", "NCURSESW5_CONFIG=false"), recipe.environment)

    def test_target_runner_resolves_absolute_loader_symlink_in_sysroot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.output = tmp / "output"
            builder.toolchain = builder.output / "toolchain"
            builder.sysroot = builder.toolchain / "sysroot"
            builder.llvm_bin = builder.toolchain / "llvm/bin"
            builder.host = builder.output / "host"
            builder.host_bin = builder.output / "host/bin"
            builder.arch = "x86_64"
            builder.triple = "x86_64-linux-musl"
            loader = builder.sysroot / "usr/lib/libc.so"
            loader.parent.mkdir(parents=True)
            loader.write_text("#!/bin/sh\nshift 2\nexec \"$@\"\n")
            loader.chmod(0o755)
            (builder.sysroot / "lib").mkdir()
            (builder.sysroot / "lib/ld-musl-x86_64.so.1").symlink_to("/usr/lib/libc.so")
            program = tmp / "program"
            program.write_text("#!/bin/sh\nprintf 'target runner works\\n'\n")
            program.chmod(0o755)
            builder.write_cross_files()
            test_bin = tmp / "test-bin"
            test_bin.mkdir()
            (test_bin / "readlink").symlink_to("/usr/bin/readlink")
            output = subprocess.check_output(
                [builder.output / "generated/run-target", program],
                text=True,
                env={"PATH": str(test_bin)},
            )
            self.assertEqual("target runner works\n", output)
            native = (builder.output / "generated/meson-native.ini").read_text()
            self.assertIn("pkg-config = '" + str(builder.output / "generated/pkgconf-native") + "'", native)
            wrapper = (builder.output / "generated/pkgconf-native").read_text()
            self.assertIn("unset PKG_CONFIG", wrapper)
            self.assertIn(str(builder.host / "lib/pkgconfig"), wrapper)

    def test_target_libc_symbol_probe_uses_dynamic_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            libc = tmp / "sysroot/lib/libc.so"
            libc.parent.mkdir(parents=True)
            libc.write_text("elf")
            llvm_bin = tmp / "llvm/bin"
            llvm_bin.mkdir(parents=True)
            nm = llvm_bin / "llvm-nm"
            nm.write_text("#!/bin/sh\nprintf '%s\n' '0000 T malloc' '0001 T __cxa_thread_atexit_impl'\n")
            nm.chmod(0o755)
            self.assertTrue(libc_defines_symbol(llvm_bin, tmp / "sysroot", "__cxa_thread_atexit_impl"))
            self.assertFalse(libc_defines_symbol(llvm_bin, tmp / "sysroot", "missing_symbol"))

    def test_runtime_driver_plan_selects_lld_and_rejects_host_gcc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            llvm_bin = tmp / "llvm/bin"
            llvm_bin.mkdir(parents=True)
            clang = llvm_bin / "clang++"
            clang.write_text("#!/bin/sh\nprintf '%s\n' 'ld.lld --rtlib=compiler-rt --unwindlib=none'\n")
            clang.chmod(0o755)
            trace = verify_runtime_driver_plan(llvm_bin, "x86_64-linux-musl", tmp / "sysroot", tmp / "build")
            self.assertIn("ld.lld", trace)
            clang.write_text("#!/bin/sh\nprintf '%s\n' 'ld.lld /usr/bin/ld crtbeginS.o -lgcc -latomic'\n")
            with self.assertRaisesRegex(RuntimeError, "leaks host/GCC inputs"):
                verify_runtime_driver_plan(llvm_bin, "x86_64-linux-musl", tmp / "sysroot", tmp / "build2")

    def test_generated_libcxx_link_plan_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            llvm_bin = tmp / "llvm/bin"
            llvm_bin.mkdir(parents=True)
            link = tmp / "build/libcxx/src/CMakeFiles/cxx_shared.dir/link.txt"
            link.parent.mkdir(parents=True)
            link.write_text(
                f"{llvm_bin / 'clang++'} -fuse-ld=lld --rtlib=compiler-rt "
                "--unwindlib=none -shared objects -o libc++.so\n"
            )
            self.assertEqual(link, verify_runtime_link_plan(tmp / "build", llvm_bin))
            link.write_text(f"{llvm_bin / 'clang++'} /usr/bin/ld -lgcc -shared\n")
            with self.assertRaisesRegex(RuntimeError, "misses required driver flags|forbidden"):
                verify_runtime_link_plan(tmp / "build", llvm_bin)

    def test_generated_package_build_plan_rejects_host_linker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            build = tmp / "build"
            (build / "CMakeFiles").mkdir(parents=True)
            compiler = "/toolchain/bin/x86_64-linux-musl-cc"
            (build / "build.ninja").write_text(f"command = {compiler} -fuse-ld=lld input.c -o output\n")
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.output = tmp / "output"
            recipe = Recipe(
                name="probe", version="1", source="probe", kind="target",
                build_system="cmake", dependencies=(), configure_args=(), cppflags=(),
                special=None, path=tmp / "probe.toml",
            )
            builder.audit_generated_build_plan(recipe, build, {"CC": compiler})
            self.assertTrue((builder.output / "reports/generated-build-plans/probe.json").exists())
            (build / "build.ninja").write_text(f"command = {compiler} /usr/bin/ld -lgcc input.o\n")
            with self.assertRaisesRegex(RuntimeError, "generated build plan leaks"):
                builder.audit_generated_build_plan(recipe, build, {"CC": compiler})

    def test_generated_package_build_plan_accepts_meson_data_only_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            build = tmp / "build"
            info = build / "meson-info"
            info.mkdir(parents=True)
            (build / "build.ninja").write_text("command = python3 generate.py\n")
            (info / "intro-targets.json").write_text(
                '[{"target_sources":[{"language":"unknown"}]}]\n'
            )
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.output = tmp / "output"
            recipe = Recipe(
                name="data", version="1", source="data", kind="target",
                build_system="meson", dependencies=(), configure_args=(), cppflags=(),
                special=None, path=tmp / "data.toml",
            )
            builder.audit_generated_build_plan(recipe, build, {"CC": "/target/cc"})
            report = (builder.output / "reports/generated-build-plans/data.json").read_text()
            self.assertIn('"status": "data-only-ok"', report)

    def test_all_package_parameters_pass_offline_audit(self) -> None:
        recipes = load_recipes()
        report = audit_static_recipes(recipes)
        self.assertEqual(len(recipes), len(report))
        self.assertTrue(all(item["status"] == "static-ok" for item in report))

    def test_glib_2_84_uses_canonical_feature_values(self) -> None:
        recipe = load_recipes()["glib"]
        self.assertIn("-Ddtrace=disabled", recipe.configure_args)
        self.assertIn("-Dsystemtap=disabled", recipe.configure_args)
        self.assertNotIn("-Ddtrace=false", recipe.configure_args)
        self.assertNotIn("-Dsystemtap=false", recipe.configure_args)

    def test_glib_source_preflight_matches_2_84_meson_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "glib"
            source.mkdir()
            (source / "meson.build").write_text("project('glib', 'c')\n")
            (source / "meson.options").write_text(
                "option('tests', type: 'boolean', value: true)\n"
                "option('installed_tests', type: 'boolean', value: false)\n"
                "option('selinux', type: 'feature', value: 'auto')\n"
                "option('libmount', type: 'feature', value: 'auto')\n"
                "option('xattr', type: 'boolean', value: true)\n"
                "option('man-pages', type: 'feature', value: 'auto')\n"
                "option('dtrace', type: 'feature', value: 'auto', "
                "deprecated: {'true': 'enabled', 'false': 'disabled'})\n"
                "option('systemtap', type: 'feature', value: 'auto', "
                "deprecated: {'true': 'enabled', 'false': 'disabled'})\n"
                "option('gtk_doc', type: 'boolean', value: false)\n"
            )
            recipe = load_recipes()["glib"]
            report = audit_source_recipes({"glib": recipe}, {"glib": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])

    def test_meson_feature_accepts_only_source_declared_legacy_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "meson-project"
            source.mkdir()
            (source / "meson.build").write_text("project('probe', 'c')\n")
            (source / "meson.options").write_text(
                "option('legacy_feature', type: 'feature', value: 'auto', "
                "deprecated: {'true': 'enabled', 'false': 'disabled'})\n"
                "option('strict_feature', type: 'feature', value: 'auto')\n"
            )
            base = load_recipes()["glib"]
            legacy = replace(base, configure_args=("-Dlegacy_feature=false",))
            report = audit_source_recipes({"glib": legacy}, {"glib": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])
            strict = replace(base, configure_args=("-Dstrict_feature=false",))
            with self.assertRaisesRegex(BuildError, "strict_feature has invalid value false"):
                audit_source_recipes({"glib": strict}, {"glib": source})

    def test_meson_option_parser_handles_triple_quoted_descriptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name)
            (source / "meson.build").write_text("project('probe', 'c')\n")
            (source / "meson.options").write_text(
                "option(\n  'first',\n  type: 'feature',\n"
                "  description: '''It's allowed (and expected).''',\n)\n"
                "option('second', type: 'boolean', value: false)\n"
            )
            self.assertEqual(["first", "second"], sorted(_meson_options(source)))



    def test_libarchive_installs_pkgconfig_metadata_in_standard_libdir(self) -> None:
        recipe = load_recipes()["libarchive"]
        self.assertIn("-DCMAKE_INSTALL_LIBDIR=lib", recipe.configure_args)






    def test_recipe_environment_expands_build_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            recipe = replace(
                load_recipes()["zlib"],
                configure_args=(),
                build_args=(),
                install_args=(),
                environment=("PROBE_PATH={sysroot}/usr/bin/probe",),
            )
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.output = tmp / "output"
            builder.host = tmp / "host"
            builder.host_bin = builder.host / "bin"
            builder.cmake_bin = tmp / "cmake/bin"
            builder.toolchain = tmp / "toolchain"
            builder.llvm_bin = builder.toolchain / "llvm/bin"
            builder.sysroot = builder.toolchain / "sysroot"
            builder.epoch = "0"
            builder.arch = "x86_64"
            builder.triple = "x86_64-linux-musl"
            builder.parallel = 1
            env = builder.base_env("target", recipe, {"sysroot": str(builder.sysroot)})
            self.assertEqual(
                str(builder.sysroot / "usr/bin/probe"),
                env["PROBE_PATH"],
            )
            builder.write_effective_parameters(recipe, None, env, {"sysroot": str(builder.sysroot)})
            report = builder.output / "reports/effective-build-parameters/zlib.json"
            self.assertIn('"PROBE_PATH": "' + str(builder.sysroot / "usr/bin/probe") + '"', report.read_text())

    def test_resume_reuses_only_matching_package_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            builder = PackageBuilder.__new__(PackageBuilder)
            build = tmp / "work/build"
            build.mkdir(parents=True)
            artifact = build / "artifact"
            artifact.write_text("partial build")
            marker = build.parent / ".strata-build-fingerprint"
            marker.write_text("matching\n")
            self.assertTrue(builder.prepare_build_directory(build, "matching\n", True))
            self.assertTrue(artifact.exists())
            self.assertFalse(builder.prepare_build_directory(build, "changed\n", True))
            self.assertFalse(artifact.exists())
            self.assertEqual("changed\n", marker.read_text())

    def test_package_build_writes_resume_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            recipe = Recipe(
                name="probe", version="1", source=None, kind="target",
                build_system="special", dependencies=(), configure_args=(),
                cppflags=(), special="busybox", path=tmp / "probe.toml",
            )
            builder = PackageBuilder.__new__(PackageBuilder)
            builder.output = tmp / "output"
            builder.recipes = {"probe": recipe}
            with patch.object(builder, "build_one") as build_one:
                builder.build(["probe"], preflight=False, resume=True)
            build_one.assert_called_once_with(recipe, resume=True)
            checkpoint = (builder.output / "reports/package-build-state.json").read_text()
            self.assertIn('"completed": [\n    "probe"\n  ]', checkpoint)
            self.assertIn('"resume": true', checkpoint)
            self.assertIn('"status": "complete"', checkpoint)

    def test_package_resume_is_available_in_build_entry_points(self) -> None:
        builder = (ROOT / "scripts/package_builder.py").read_text()
        dispatcher = (ROOT / "scripts/build.py").read_text()
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("package-build-state.json", builder)
        self.assertIn('parser.add_argument("--resume"', builder)
        self.assertIn('parser.add_argument("--resume"', dispatcher)
        self.assertIn("RESUME ?= 1", makefile)


    def test_sqlite_3_50_1_uses_autoconf_bundle_options(self) -> None:
        recipe = load_recipes()["sqlite"]
        self.assertEqual("3.50.1", recipe.version)
        self.assertEqual("autotools", recipe.build_system)
        self.assertEqual(
            (
                "--disable-static",
                "--enable-shared",
                "--disable-static-shell",
                "--disable-readline",
            ),
            recipe.configure_args,
        )
        self.assertNotIn("--disable-editline", recipe.configure_args)
        self.assertNotIn("--disable-tcl", recipe.configure_args)

    def test_sqlite_3_50_1_source_preflight_matches_autoconf_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "sqlite"
            source.mkdir()
            configure = source / "configure"
            configure.write_text(
                "#!/bin/sh\n"
                "cat <<'EOF'\n"
                "  --disable-static         Disable build of static library\n"
                "  --disable-shared         Disable build of shared library\n"
                "  --disable-static-shell   Link sqlite3 shell against the DLL\n"
                "  --disable-readline       Disable readline support\n"
                "EOF\n"
            )
            configure.chmod(0o755)
            recipe = load_recipes()["sqlite"]
            report = audit_source_recipes({"sqlite": recipe}, {"sqlite": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])
            for obsolete_option in ("--disable-editline", "--disable-tcl"):
                with self.subTest(option=obsolete_option):
                    obsolete = replace(recipe, configure_args=(obsolete_option,))
                    with self.assertRaisesRegex(BuildError, "configure option is not advertised"):
                        audit_source_recipes({"sqlite": obsolete}, {"sqlite": source})

    def test_procps_4_0_5_minimal_parameter_contract(self) -> None:
        recipe = load_recipes()["procps-ng"]
        self.assertEqual(
            (
                "--disable-static",
                "--enable-shared",
                "--disable-nls",
                "--disable-kill",
                "--disable-w",
                "--disable-skill",
                "--disable-pidof",
                "--disable-pidwait",
                "--without-ncurses",
                "--without-systemd",
                "--without-elogind",
            ),
            recipe.configure_args,
        )

    def test_procps_4_0_5_uses_release_tarball_with_configure(self) -> None:
        recipe = load_recipes()["procps-ng"]
        self.assertEqual("autotools", recipe.build_system)
        source = recipe.source_for_arch("x86_64")
        self.assertEqual(
            "https://downloads.sourceforge.net/project/procps-ng/Production/"
            "procps-ng-{version}.tar.xz",
            source.url,
        )
        self.assertNotIn("/-/archive/", source.url)
        self.assertEqual(
            "c2e6d193cc78f84cd6ddb72aaf6d5c6a9162f0470e5992092057f5ff518562fa",
            source.sha256,
        )

    def test_procps_4_0_5_release_layout_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "procps-ng"
            source.mkdir()
            configure = source / "configure"
            configure.write_text(
                "#!/bin/sh\n"
                "cat <<'EOF'\n"
                "  --disable-static\n"
                "  --enable-shared\n"
                "  --disable-nls\n"
                "  --disable-kill\n"
                "  --disable-w\n"
                "  --disable-skill\n"
                "  --disable-pidof\n"
                "  --disable-pidwait\n"
                "  --without-ncurses\n"
                "  --without-systemd\n"
                "  --without-elogind\n"
                "EOF\n"
            )
            configure.chmod(0o755)
            recipe = load_recipes()["procps-ng"]
            report = audit_source_recipes({"procps-ng": recipe}, {"procps-ng": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])

    def test_nftables_1_1_3_uses_root_autotools_without_python_switch(self) -> None:
        recipe = load_recipes()["nftables"]
        self.assertEqual(
            ("--disable-man-doc", "--with-json", "--with-cli=readline"),
            recipe.configure_args,
        )
        self.assertNotIn("--disable-python", recipe.configure_args)
        self.assertNotIn("--enable-python", recipe.configure_args)
        source = load_recipes()["nftables"].source_for_arch("x86_64")
        self.assertEqual(
            "9c8a64b59c90b0825e540a9b8fcb9d2d942c636f81ba50199f068fde44f34ed8",
            source.sha256,
        )

    def test_nftables_1_1_3_source_preflight_matches_configure_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "nftables"
            source.mkdir()
            configure = source / "configure"
            configure.write_text(
                "#!/bin/sh\n"
                "cat <<'EOF'\n"
                "  --disable-man-doc       Disable man page documentation\n"
                "  --with-json             Enable JSON support\n"
                "  --with-cli=TYPE         Select CLI implementation\n"
                "EOF\n"
            )
            configure.chmod(0o755)
            recipe = load_recipes()["nftables"]
            report = audit_source_recipes({"nftables": recipe}, {"nftables": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])
            obsolete = replace(recipe, configure_args=("--disable-python",))
            with self.assertRaisesRegex(BuildError, "enable-python"):
                audit_source_recipes({"nftables": obsolete}, {"nftables": source})

    def test_dbus_1_16_uses_declared_meson_test_options(self) -> None:
        recipe = load_recipes()["dbus"]
        self.assertNotIn("-Dtests=false", recipe.configure_args)
        for argument in (
            "-Dintrusive_tests=false",
            "-Dmodular_tests=disabled",
            "-Dinstalled_tests=false",
        ):
            self.assertIn(argument, recipe.configure_args)
        source = load_recipes()["dbus"].source_for_arch("x86_64")
        self.assertEqual(
            "0ba2a1a4b16afe7bceb2c07e9ce99a8c2c3508e5dec290dbb643384bd6beb7e2",
            source.sha256,
        )

    def test_dbus_source_preflight_matches_1_16_meson_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "dbus"
            source.mkdir()
            (source / "meson.build").write_text("project('dbus', 'c')\n")
            feature_options = (
                "systemd", "selinux", "apparmor", "libaudit",
                "modular_tests", "xml_docs", "doxygen_docs",
                "ducktype_docs", "x11_autolaunch",
            )
            boolean_options = ("intrusive_tests", "installed_tests", "tools")
            blocks = [
                f"option('{name}', type: 'feature', value: 'auto')"
                for name in feature_options
            ] + [
                f"option('{name}', type: 'boolean', value: false)"
                for name in boolean_options
            ]
            (source / "meson_options.txt").write_text("\n".join(blocks) + "\n")
            recipe = load_recipes()["dbus"]
            report = audit_source_recipes({"dbus": recipe}, {"dbus": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])
            obsolete = replace(recipe, configure_args=("-Dtests=false",))
            with self.assertRaisesRegex(RuntimeError, "Meson option is not declared.*tests"):
                audit_source_recipes({"dbus": obsolete}, {"dbus": source})

    def test_toolchain_requires_source_aware_preflight(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("toolchain: preflight", makefile)
        self.assertIn("preflight: source-probe", makefile)

    def test_cmake_preflight_accepts_custom_cache_setter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "expat"
            source.mkdir()
            (source / "CMakeLists.txt").write_text(
                "macro(expat_shy_set var default cache type desc)\n"
                "  if(NOT ${cache} STREQUAL \"CACHE\")\n"
                "    message(SEND_ERROR \"invalid cache declaration\")\n"
                "  endif()\n"
                "  set(\"${var}\" \"${default}\" CACHE \"${type}\" \"${desc}\")\n"
                "endmacro()\n"
                "expat_shy_set(EXPAT_BUILD_TOOLS ON CACHE BOOL \"tools\")\n"
                "expat_shy_set(EXPAT_BUILD_EXAMPLES ON CACHE BOOL \"examples\")\n"
                "expat_shy_set(EXPAT_BUILD_TESTS ON CACHE BOOL \"tests\")\n"
                "expat_shy_set(EXPAT_BUILD_DOCS OFF CACHE BOOL \"docs\")\n"
            )
            recipe = load_recipes()["expat"]
            report = audit_source_recipes({"expat": recipe}, {"expat": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])



    def test_cmake_preflight_still_rejects_undeclared_custom_cache_variable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "cmake-project"
            source.mkdir()
            (source / "CMakeLists.txt").write_text(
                "macro(project_cache_set var default cache type desc)\n"
                "  set(\"${var}\" \"${default}\" CACHE \"${type}\" \"${desc}\")\n"
                "endmacro()\n"
                "project_cache_set(DECLARED_OPTION OFF CACHE BOOL \"declared\")\n"
            )
            recipe = replace(
                load_recipes()["expat"],
                configure_args=("-DDECLARED_OPTION=OFF", "-DUNDECLARED_OPTION=OFF"),
            )
            with self.assertRaisesRegex(BuildError, "UNDECLARED_OPTION"):
                audit_source_recipes({"expat": recipe}, {"expat": source})

    def test_cmake_preflight_scans_nested_cmakelists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "cmake-project"
            (source / "subproject").mkdir(parents=True)
            (source / "CMakeLists.txt").write_text("add_subdirectory(subproject)\n")
            (source / "subproject/CMakeLists.txt").write_text(
                "option(NESTED_FEATURE \"nested feature\" OFF)\n"
            )
            recipe = replace(
                load_recipes()["expat"],
                configure_args=("-DNESTED_FEATURE=OFF",),
            )
            report = audit_source_recipes({"expat": recipe}, {"expat": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])

    def test_openrc_0_56_uses_meson_and_declares_linux_dependencies(self) -> None:
        recipe = load_recipes()["openrc"]
        self.assertEqual("meson", recipe.build_system)
        self.assertIsNone(recipe.special)
        self.assertIn("libcap", recipe.dependencies)
        self.assertIn("musl-runtime", recipe.dependencies)
        self.assertIn("-Dos=Linux", recipe.configure_args)
        self.assertIn("-Daudit=disabled", recipe.configure_args)
        self.assertIn("-Dpam=false", recipe.configure_args)
        self.assertIn("-Dselinux=disabled", recipe.configure_args)
        self.assertIn("-Dnewnet=false", recipe.configure_args)

    def test_openrc_0_56_source_preflight_matches_meson_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "openrc"
            source.mkdir()
            (source / "meson.build").write_text(
                "project('OpenRC', 'c', version : '0.56')\n"
            )
            (source / "meson_options.txt").write_text(
                "option('audit', type : 'feature', value : 'auto')\n"
                "option('bash-completions', type : 'boolean')\n"
                "option('branding', type : 'string')\n"
                "option('local_prefix', type : 'string', value : '/usr/local')\n"
                "option('newnet', type : 'boolean')\n"
                "option('os', type : 'combo', choices : ['', 'Linux'])\n"
                "option('pam', type : 'boolean')\n"
                "option('pkg_prefix', type : 'string')\n"
                "option('pkgconfig', type : 'boolean')\n"
                "option('selinux', type : 'feature', value : 'auto')\n"
                "option('shell', type : 'string', value : '/bin/sh')\n"
                "option('sysvinit', type : 'boolean', value : false)\n"
                "option('zsh-completions', type : 'boolean')\n"
            )
            recipe = load_recipes()["openrc"]
            report = audit_source_recipes({"openrc": recipe}, {"openrc": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])

            legacy = replace(
                recipe, build_system="special", special="openrc", configure_args=()
            )
            with self.assertRaisesRegex(BuildError, "missing source path Makefile"):
                audit_source_recipes({"openrc": legacy}, {"openrc": source})

    def test_busybox_uses_native_kconfig_layout_without_linux_scripts_config(self) -> None:
        self.assertEqual(("Makefile", "scripts/kconfig/Makefile"), SPECIAL_CONTRACTS["busybox"])
        source = (ROOT / "scripts/package_builder.py").read_text()
        self.assertNotIn('source / "scripts/config"', source)
        self.assertIn("apply_kconfig_fragment", source)
        self.assertIn("verify_kconfig_fragment", source)

    def test_busybox_source_preflight_accepts_native_kconfig_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            source = Path(tmp_name) / "busybox"
            (source / "scripts/kconfig").mkdir(parents=True)
            (source / "Makefile").write_text("all:\n\t@true\n")
            (source / "scripts/kconfig/Makefile").write_text("all:\n\t@true\n")
            recipe = load_recipes()["busybox"]
            report = audit_source_recipes({"busybox": recipe}, {"busybox": source})
            self.assertEqual("source-options-ok", report[0]["source_status"])

    def test_busybox_does_not_shadow_util_linux_blkid(self) -> None:
        fragment = load_recipes()["busybox"].config_path("busybox.fragment").read_text()
        self.assertIn("CONFIG_BLKID=n", fragment.splitlines())
        self.assertIn("CONFIG_MOUNT=n", fragment.splitlines())
        self.assertIn("CONFIG_UMOUNT=n", fragment.splitlines())
        self.assertIn("CONFIG_LOSETUP=n", fragment.splitlines())
        self.assertIn("CONFIG_TEST1=y", fragment.splitlines())
        self.assertIn("CONFIG_FEATURE_TEST_64=y", fragment.splitlines())
        self.assertIn("CONFIG_ASH_TEST=y", fragment.splitlines())

        self.assertIn("CONFIG_BLOCKDEV=y", fragment.splitlines())
        self.assertIn("CONFIG_CP=y", fragment.splitlines())
        initramfs_builder = (ROOT / "scripts/initramfs.py").read_text()
        self.assertIn('"blkid", "blockdev", "lsblk"', initramfs_builder)

        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            (root / "bin").mkdir()
            (root / "sbin").mkdir()
            (root / "bin/busybox").touch()
            (root / "sbin/blkid").symlink_to("../bin/busybox")
            with self.assertRaisesRegex(BuildError, "requires util-linux blkid"):
                validate_util_linux_tools(root)
            (root / "sbin/blkid").unlink()
            (root / "bin/mount").symlink_to("busybox")
            with self.assertRaisesRegex(BuildError, "requires util-linux mount"):
                validate_util_linux_tools(root)
            (root / "bin/mount").unlink()
            (root / "sbin/losetup").symlink_to("../bin/busybox")
            with self.assertRaisesRegex(BuildError, "requires util-linux losetup"):
                validate_util_linux_tools(root)
            (root / "sbin/losetup").unlink()
            (root / "sbin/switch_root").symlink_to("../bin/busybox")
            with self.assertRaisesRegex(BuildError, "requires util-linux switch_root"):
                validate_util_linux_tools(root)

        self.assertIn("shutil.copy2(util_switch_root, staged_switch_root)", initramfs_builder)

    def test_openrc_proc_probe_uses_busybox_md5sum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            install_base_configuration(root, self.x86)
            self.assertEqual("busybox", os.readlink(root / "bin/md5sum"))

    def test_base_accounts_require_root_initial_setup(self) -> None:
        self.assertFalse((ROOT / "SOURCE-MANIFEST.sha256").exists())
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            install_base_configuration(root, self.x86)
            passwd = (root / "etc/passwd").read_text().splitlines()
            shadow = (root / "etc/shadow").read_text().splitlines()
            self.assertFalse(any(line.startswith("strata:") for line in passwd))
            root_shadow = next(line for line in shadow if line.startswith("root:"))
            self.assertTrue(root_shadow.startswith("root:$6$strataos$"))
            for name in ("passwd", "group", "shadow", "gshadow"):
                self.assertTrue((root / "etc" / name).is_file())
                self.assertFalse((root / "etc" / name).is_symlink())
            self.assertFalse((root / "home/strata").exists())
            self.assertTrue((root / "var/spool/mail").is_dir())
            self.assertEqual("spool/mail", os.readlink(root / "var/mail"))
            self.assertTrue(
                any(line.startswith("mail:x:12:") for line in (root / "etc/group").read_text().splitlines())
            )

        for path in (
            ROOT / "defconfigs/x86_64_defconfig",
            ROOT / "defconfigs/arm64_defconfig",
        ):
            text = path.read_text()
            self.assertNotIn("STRATA_DEFAULT_USER", text)
            self.assertNotIn("STRATA_ENABLE_OPENSSH", text)

        legacy = dict(self.x86, STRATA_ENABLE_OPENSSH="1")
        with self.assertRaisesRegex(BuildError, "removed configuration keys"):
            validate(legacy, native=False)

    def test_zsh_completion_directories_are_not_group_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            functions = root / "usr/share/zsh/5.9/functions"
            functions.mkdir(parents=True)
            (root / "usr/share/zsh").chmod(0o775)
            (root / "usr/share/zsh/5.9").chmod(0o777)
            functions.chmod(0o755)

            install_base_configuration(root, self.x86)

            self.assertEqual(0o755, (root / "usr/share/zsh").stat().st_mode & 0o777)
            self.assertEqual(0o755, (root / "usr/share/zsh/5.9").stat().st_mode & 0o777)
            self.assertEqual(0o755, functions.stat().st_mode & 0o777)

    def test_busybox_fragment_editor_handles_bool_string_and_integer_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            config = tmp / ".config"
            fragment = tmp / "busybox.fragment"
            config.write_text(
                "# CONFIG_ALPHA is not set\n"
                "CONFIG_BETA=y\n"
                "CONFIG_KEEP=42\n"
            )
            fragment.write_text(
                "CONFIG_ALPHA=y\n"
                "CONFIG_BETA=n\n"
                'CONFIG_TEXT="strata"\n'
                "CONFIG_COUNT=7\n"
            )
            requested = apply_kconfig_fragment(config, fragment)
            self.assertEqual(
                {"ALPHA": "y", "BETA": "n", "TEXT": '"strata"', "COUNT": "7"},
                requested,
            )
            self.assertEqual(
                {
                    "ALPHA": "y", "BETA": "n", "KEEP": "42",
                    "TEXT": '"strata"', "COUNT": "7",
                },
                read_kconfig_values(config),
            )
            verify_kconfig_fragment(config, requested)

    def test_busybox_fragment_verifier_rejects_dependency_drops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            config = Path(tmp_name) / ".config"
            config.write_text("# CONFIG_REQUIRED is not set\n")
            with self.assertRaisesRegex(RuntimeError, "requested y, effective n"):
                verify_kconfig_fragment(config, {"REQUIRED": "y"})

    def test_package_fingerprint_tracks_handler_and_local_inputs(self) -> None:
        source = (ROOT / "scripts/package_builder.py").read_text()
        self.assertIn('digest.update(b"package-fingerprint-v2', source)
        self.assertIn('ROOT / "scripts/package_builder.py"', source)
        self.assertIn('ROOT / "scripts/build_policy.py"', source)
        self.assertIn('recipe.config_path("busybox.fragment")', source)
        self.assertIn('recipe.build_system == "local"', source)
        self.assertIn('recipe.path.parent.rglob("*")', source)


    def test_global_target_policy_forbids_host_runtime_fallbacks(self) -> None:
        self.assertIn("-fuse-ld=lld", TARGET_LINK_FLAGS)
        self.assertIn("--rtlib=compiler-rt", TARGET_LINK_FLAGS)
        self.assertIn("--unwindlib=libunwind", TARGET_CXX_LINK_FLAGS)
        for key in ("CPATH", "LIBRARY_PATH", "LD_LIBRARY_PATH", "CMAKE_PREFIX_PATH"):
            self.assertEqual("", SANITIZED_ENVIRONMENT[key])

    def test_runtime_configuration_disables_gcc_and_atomic_fallbacks(self) -> None:
        source = (ROOT / "scripts/bootstrap_toolchain.py").read_text()
        self.assertIn('"-DLIBCXX_HAS_ATOMIC_LIB=OFF"', source)
        self.assertIn('"-DLIBCXX_HAS_PTHREAD_API=ON"', source)
        self.assertIn('"-DLIBCXX_HAS_RT_LIB=OFF"', source)
        self.assertIn('"-DLIBCXX_HAS_PTHREAD_LIB=OFF"', source)
        for removed in (
            "LIBCXX_HAS_GCC_LIB", "LIBCXX_HAS_C_LIB", "LIBCXX_HAS_M_LIB",
            "LIBCXXABI_HAS_DL_LIB", "LIBUNWIND_HAS_C_LIB",
        ):
            self.assertNotIn(f'"-D{removed}=', source)
        self.assertIn('"-DLIBCXXABI_HAS_C_LIB=ON"', source)
        self.assertIn('"-DLIBCXXABI_HAS_PTHREAD_LIB=OFF"', source)
        self.assertIn('"-DLIBUNWIND_HAS_DL_LIB=OFF"', source)
        self.assertIn("verify_runtime_cmake_variable_references", source)
        self.assertIn("verify_runtime_driver_plan", source)
        self.assertIn("verify_runtime_link_plan", source)
        self.assertIn('"bootstrap_schema=10"', source)
        self.assertIn("missing_cxx_runtime_libraries(sysroot)", source)
        self.assertIn("toolchain cache is missing target C++ runtime libraries", source)
        builder = (ROOT / "scripts/package_builder.py").read_text()
        self.assertIn("has_llvm_runtime_libraries(root)", builder)

    def test_recipe_corrections_cover_known_cross_build_conflicts(self) -> None:
        recipes = load_recipes()
        self.assertIn("--without-normal", recipes["ncurses"].configure_args)
        self.assertIn("--with-build-cc={host_cc}", recipes["ncurses"].configure_args)
        self.assertIn("host-ncurses", recipes["ncurses"].dependencies)
        self.assertIn("--with-tic-path={host}/libexec/host-ncurses/bin/tic", recipes["ncurses"].configure_args)
        self.assertNotIn("--disable-db-install", recipes["ncurses"].configure_args)
        self.assertIn("--disable-libuuid", recipes["e2fsprogs"].configure_args)
        self.assertIn("--disable-libblkid", recipes["e2fsprogs"].configure_args)
        self.assertNotIn("--with-ssl-engine", recipes["openssh"].configure_args)

    def test_preflight_and_post_link_audits_are_in_build_pipeline(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        builder = (ROOT / "scripts/package_builder.py").read_text()
        self.assertIn("make preflight", makefile)
        self.assertIn("builder.preflight(requested)", builder)
        self.assertIn("run_build_system_probes", builder)
        self.assertIn("effective-build-parameters", builder)
        self.assertIn("generated-build-plans", builder)
        self.assertIn("audit_generated_build_plan", builder)
        self.assertIn("manually specified variables", builder.lower())
        self.assertIn("audit_elf_tree", builder)
        self.assertIn("verify_needed_closure", builder)

    def test_compiler_rt_candidate_prefers_native_linux_archive(self) -> None:
        native = Path("lib/clang/22/lib/x86_64-unknown-linux-gnu/libclang_rt.builtins.a")
        android = Path("lib/clang/22/lib/x86_64-linux-android/libclang_rt.builtins.a")
        other = Path("lib/clang/22/lib/aarch64-unknown-linux-gnu/libclang_rt.builtins.a")
        self.assertGreater(
            _runtime_candidate_score(native, "x86_64"),
            _runtime_candidate_score(android, "x86_64"),
        )
        self.assertGreater(
            _runtime_candidate_score(native, "x86_64"),
            _runtime_candidate_score(other, "x86_64"),
        )

    def test_direct_child_make_drops_makelevel_and_jobserver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            make = tmp / "make"
            output = tmp / "environment"
            make.write_text(
                "#!/bin/sh\n"
                "printf '%s\n' \"${MAKEFLAGS-unset}\" \"${GNUMAKEFLAGS-unset}\" \"${MAKELEVEL-unset}\" > \"$1\"\n"
            )
            make.chmod(0o755)
            run(
                [str(make), str(output)],
                env={
                    "MAKEFLAGS": "w -j8 --jobserver-auth=fifo:/tmp/jobs",
                    "GNUMAKEFLAGS": "--jobs=8",
                    "MAKELEVEL": "1",
                },
            )
            values = output.read_text().splitlines()
            self.assertNotIn("jobserver", values[0])
            self.assertNotIn("-j8", values[0])
            self.assertEqual("unset", values[1])
            self.assertEqual("unset", values[2])

    def test_cmake_build_drops_parent_jobserver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            cmake = tmp / "cmake"
            output = tmp / "environment"
            cmake.write_text(
                "#!/bin/sh\n"
                "printf '%s\n' \"${MAKEFLAGS-unset}\" \"${GNUMAKEFLAGS-unset}\" \"${MAKELEVEL-unset}\" > \"$STRATA_TEST_OUTPUT\"\n"
            )
            cmake.chmod(0o755)
            run(
                [str(cmake), "--build", str(tmp / "tree"), "--parallel", "8"],
                env={
                    "STRATA_TEST_OUTPUT": str(output),
                    "MAKEFLAGS": "w -j8 --jobserver-auth=fifo:/tmp/jobs",
                    "GNUMAKEFLAGS": "--jobs=8",
                    "MAKELEVEL": "1",
                },
            )
            self.assertEqual(["unset", "unset", "unset"], output.read_text().splitlines())

    def test_child_makeflags_drop_parent_jobserver(self) -> None:
        cleaned = _makeflags_without_parallelism(
            "w -j8 --jobserver-auth=fifo:/tmp/jobs --no-print-directory"
        )
        self.assertNotIn("jobserver", cleaned)
        self.assertNotIn("-j8", cleaned)
        self.assertIn("--no-print-directory", cleaned)
        bare = _makeflags_without_parallelism("-j --no-print-directory")
        self.assertIn("--no-print-directory", bare)

    def test_makefile_documents_and_serializes_parallel_orchestration(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn(".NOTPARALLEL:", makefile)
        self.assertIn("make -j$$(nproc)", makefile)

    def test_native_recipe_graph_is_acyclic(self) -> None:
        recipes = load_recipes()
        requested = component_package_names(self.x86)
        order = topological_order(recipes, requested)
        self.assertEqual(len(order), len(set(order)))
        for name in ("busybox", "openrc", "zsh", "openssh", "docker-static"):
            self.assertIn(name, order)

    def test_component_package_ownership_is_explicit_and_unique(self) -> None:
        owners: dict[str, str] = {}
        for path in sorted((ROOT / "components").glob("*/packages.list")):
            component = path.parent.name
            for raw in path.read_text().splitlines():
                package = raw.strip()
                if not package or package.startswith("#"):
                    continue
                self.assertNotIn(package, owners)
                owners[package] = component
        self.assertEqual("system-core", owners["openrc"])
        self.assertEqual("python", owners["python"])
        self.assertEqual("openssh", owners["openssh"])
        self.assertEqual("fail2ban", owners["fail2ban"])
        self.assertEqual("network", owners["iproute2"])
        self.assertEqual("firewall", owners["nftables"])
        self.assertEqual("system-core", owners["libmnl"])
        self.assertEqual("diagnostics", owners["htop"])
        self.assertEqual("fonts-cjk", owners["noto-sans-cjk-sc"])
        self.assertEqual("docker", owners["docker-static"])

    def test_architecture_specific_sources_exist(self) -> None:
        recipes = load_recipes()
        for name in ("docker-static",):
            self.assertNotEqual(
                recipes[name].source_for_arch("x86_64").url,
                recipes[name].source_for_arch("arm64").url,
            )
        inputs = load_toolchain_inputs()
        for name in ("llvm-prebuilt", "cmake"):
            self.assertNotEqual(
                inputs[name].source_for_arch("x86_64").url,
                inputs[name].source_for_arch("arm64").url,
            )

    def test_zsh_release_uses_versioned_official_archive_and_hash(self) -> None:
        recipe = load_recipes()["zsh"]
        source = recipe.source_for_arch("x86_64")
        self.assertEqual("5.9.2", recipe.version)
        self.assertEqual(
            "https://downloads.sourceforge.net/project/zsh/zsh/{version}/zsh-{version}.tar.xz",
            source.url,
        )
        self.assertEqual(
            "36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81",
            source.sha256,
        )

    def test_source_probe_selects_current_architecture(self) -> None:
        entries = {label: (source, version) for label, source, version in inventory_entries("arm64")}
        self.assertIn("docker-static", entries)
        self.assertIn("llvm-prebuilt", entries)
        self.assertIn("aarch64", entries["docker-static"][0].url)
        self.assertIn("ARM64", entries["llvm-prebuilt"][0].url)

    def test_source_probe_reads_one_byte_and_fails_before_toolchain(self) -> None:
        class Response:
            def __init__(self) -> None:
                self.read_sizes: list[int] = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self, size: int = -1) -> bytes:
                self.read_sizes.append(size)
                return b"x"

        response = Response()
        with tempfile.TemporaryDirectory() as tmp_name, patch(
            "fetch.urllib.request.urlopen", return_value=response
        ) as opener:
            probe_source(
                "source", Source("https://example.invalid/source-{version}.tar.xz", None, None, 1),
                "1", Path(tmp_name),
            )
        self.assertEqual([1], response.read_sizes)
        request = opener.call_args.args[0]
        self.assertEqual("bytes=0-0", request.headers["Range"])
        with tempfile.TemporaryDirectory() as tmp_name, patch(
            "fetch.urllib.request.urlopen", side_effect=OSError("HTTP 404")
        ):
            with self.assertRaisesRegex(BuildError, "HTTP 404"):
                probe_source(
                    "source", Source("https://example.invalid/source-{version}.tar.xz", None, None, 1),
                    "1", Path(tmp_name),
                )
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("toolchain: preflight", makefile)
        self.assertIn("preflight: source-probe", makefile)

    def test_component_runtime_uses_component_local_volume_ids(self) -> None:
        runtime = (ROOT / "initramfs/bin/strata-componentd").read_text()
        self.assertIn('runtime_volume_id "$component" "$id"', runtime)
        self.assertIn('$1 == component && $2 == id', runtime)
        self.assertIn("allocate_file() (", runtime)

    def test_root_overlay_backing_stays_outside_moved_run_mount(self) -> None:
        runtime = (ROOT / "initramfs/bin/strata-componentd").read_text()
        self.assertIn("BACKING_STORE=/strata-backing", runtime)
        self.assertIn("OVERLAY_STORE=$BACKING_STORE/overlay", runtime)
        self.assertIn("COMPONENT_STORE=$BACKING_STORE/components", runtime)
        self.assertIn("LOWER_STORE=/l", runtime)
        self.assertIn('tmpfs "$BACKING_STORE"', runtime)
        self.assertIn('mountpoint="$COMPONENT_STORE/c$component_count"', runtime)
        self.assertIn('ln -s "$root" "$LOWER_STORE/$component_count"', runtime)
        self.assertIn("printf '%05d|%s|%s|%s", runtime)
        self.assertIn('lower="$LOWER_STORE/$sequence"', runtime)
        self.assertIn('upperdir=$OVERLAY_STORE/upper', runtime)
        self.assertIn('workdir=$OVERLAY_STORE/work', runtime)
        self.assertNotIn("upperdir=/run/", runtime)
        self.assertNotIn('mountpoint="/run/strataos/components/', runtime)
        self.assertLess(
            runtime.index('mount -t tmpfs -o mode=0755,size=50% tmpfs "$BACKING_STORE"'),
            runtime.index('mount --move /run "$NEWROOT/run"'),
        )

    def test_console_shutdown_does_not_kill_all_shells(self) -> None:
        service = (
            ROOT / "components/system-core/rootfs/etc/init.d/getty-console"
        ).read_text()
        self.assertNotIn("killall", service)

    def test_outer_data_filesystem_uses_largefile_inode_density(self) -> None:
        disk = load_data(ROOT / "configs/image/disk.conf")
        image_builder = (ROOT / "scripts/image.py").read_text()
        early_init = (ROOT / "initramfs/init").read_text()
        self.assertEqual("largefile4", disk["partition.data.usage_type"])
        self.assertIn('"-T", disk["partition.data.usage_type"]', image_builder)
        self.assertIn("errors=remount-ro,noinit_itable", early_init)

    def test_native_gpt_writer_emits_protective_mbr_and_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            first = tmp / "p1"
            second = tmp / "p2"
            first.write_bytes(b"A" * 512)
            second.write_bytes(b"B" * 512)
            image = tmp / "disk.img"
            write_gpt_image(
                image,
                8 * 1024 * 1024,
                512,
                str(uuid.uuid4()),
                [
                    {"name": "ESP", "type_guid": str(uuid.uuid4()), "guid": str(uuid.uuid4()), "first_lba": 2048, "last_lba": 4095, "image": first},
                    {"name": "DATA", "type_guid": str(uuid.uuid4()), "guid": str(uuid.uuid4()), "first_lba": 4096, "last_lba": 8191, "image": second},
                ],
            )
            body = image.read_bytes()
            self.assertEqual(b"\x55\xaa", body[510:512])
            self.assertEqual(b"EFI PART", body[512:520])
            self.assertEqual(b"A" * 16, body[2048 * 512 : 2048 * 512 + 16])

    def test_extlinux_configuration_uses_the_esp_kernel_and_initramfs(self) -> None:
        command_line = kernel_command_line(
            "arm64", "STRATA_ESP", "STRATA_DATA", "ext4"
        )
        configuration = extlinux_config(command_line)
        self.assertIn("DEFAULT strataos", configuration)
        self.assertIn("LINUX /strataos/kernel", configuration)
        self.assertIn("INITRD /strataos/initramfs.cpio.gz", configuration)
        self.assertIn(f"APPEND {command_line}", configuration)
        self.assertIn("console=ttyAMA0,115200 console=tty0", configuration)
        self.assertNotIn("clocksource=tsc", configuration)
        self.assertIn(
            "clocksource=tsc tsc=nowatchdog",
            kernel_command_line("x86_64", "ESP", "DATA", "ext4"),
        )
        limine = limine_config(command_line)
        self.assertIn("path: boot():/strataos/kernel", limine)
        self.assertIn("module_path: boot():/strataos/initramfs.cpio.gz", limine)
        self.assertIn(f"cmdline: {command_line}", limine)
        image_builder = (ROOT / "scripts/image.py").read_text()
        self.assertIn('if bootloader == "limine-efi":', image_builder)
        self.assertIn('extlinux_dir = esp_root / "extlinux"', image_builder)
        self.assertIn('esp_entries.append(extlinux_dir)', image_builder)
        self.assertIn('esp_entries.append(esp_root / "EFI")', image_builder)
        qemu = (ROOT / "scripts/qemu.py").read_text()
        self.assertIn("make qemu requires STRATA_BOOTLOADER=limine-efi", qemu)

    def test_python_newc_writer_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            root = tmp / "root"
            (root / "bin").mkdir(parents=True)
            (root / "bin/tool").write_text("tool\n")
            (root / "bin/link").symlink_to("tool")
            first = tmp / "first.cpio"
            second = tmp / "second.cpio"
            write_newc(root, first, 1234)
            write_newc(root, second, 1234)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertIn(b"TRAILER!!!", first.read_bytes())

    def test_component_metadata_applies_target_account_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            stage = tmp / "stage"
            root = stage / "rootfs"
            (root / "var/lib/dbus").mkdir(parents=True)
            (root / "var/lib/dbus").chmod(0o755)
            (root / "var/lib/dbus/machine-id").write_text("id\n")
            (stage / "meta/strataos").mkdir(parents=True)
            metadata = metadata_for_tree(root)
            self.assertEqual((0o755, 81, 81), metadata["var/lib/dbus"])
            pseudo = write_metadata_pseudo(stage, root, metadata)
            self.assertIn('"rootfs/var/lib/dbus" m 0755 81 81', pseudo.read_text())

    def test_qemu_disk_covers_declared_logical_capacity(self) -> None:
        declared = 0
        for path in (ROOT / "components").glob("*/component.conf"):
            item = load_data(path)
            for index in range(int(item.get("storage.count", "0"))):
                declared += int(item[f"storage.{index}.initial_size_mib"])
        self.assertGreaterEqual(qemu_disk_mib(self.x86), declared + 2048)
        undersized = dict(self.x86)
        undersized["STRATA_QEMU_DISK_MIB"] = str(declared + 2048 - 4096)
        with self.assertRaises(BuildError):
            qemu_disk_mib(undersized)

    def test_qemu_uses_kvm_only_for_a_matching_host_architecture(self) -> None:
        self.assertEqual(
            ["-accel", "kvm", "-cpu", "host"],
            qemu_acceleration_args(
                "x86_64", kvm_accessible=True, host_arch="x86_64"
            ),
        )
        self.assertEqual(
            ["-accel", "tcg", "-cpu", "max"],
            qemu_acceleration_args(
                "x86_64", kvm_accessible=False, host_arch="x86_64"
            ),
        )
        self.assertEqual(
            ["-accel", "tcg", "-cpu", "cortex-a72"],
            qemu_acceleration_args(
                "arm64", kvm_accessible=True, host_arch="x86_64"
            ),
        )

    def test_qemu_uses_two_virtual_cpus(self) -> None:
        source = (ROOT / "scripts/qemu.py").read_text()
        self.assertIn('"-smp", "2"', source)

    def test_qemu_prioritizes_disk_and_refreshes_vars_for_topology(self) -> None:
        source = (ROOT / "scripts/qemu.py").read_text()
        self.assertIn("virtio-blk-pci,drive=strata_disk,bootindex=1", source)
        self.assertIn("virtio-net-pci,netdev=net0,bootindex=2", source)
        self.assertIn('"-boot", "order=c,strict=on"', source)
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            output = tmp / "output"
            (output / "images").mkdir(parents=True)
            template = tmp / "OVMF_VARS.fd"
            raw = tmp / "strataos.img"
            template.write_bytes(b"clean-vars")
            raw.write_bytes(b"image")
            destination = prepare_vars(template, output, raw, "serial")
            destination.write_bytes(b"saved-vars")
            self.assertEqual(destination, prepare_vars(template, output, raw, "serial"))
            self.assertEqual(b"saved-vars", destination.read_bytes())
            prepare_vars(template, output, raw, "virgl")
            self.assertEqual(b"clean-vars", destination.read_bytes())

    def test_qemu_exposes_a_headless_virgl_render_node_by_default(self) -> None:
        source = (ROOT / "scripts/qemu.py").read_text()
        self.assertIn('"egl-headless,gl=on"', source)
        self.assertIn('"virtio-gpu-gl-pci"', source)
        self.assertIn('os.environ.get("STRATA_QEMU_GPU", "virgl")', source)

    def test_foreground_services_do_not_block_openrc_runlevel_startup(self) -> None:
        getty = (
            ROOT / "components/system-core/rootfs/etc/init.d/getty-console"
        ).read_text()
        docker = (ROOT / "components/docker/rootfs/etc/init.d/docker").read_text()
        self.assertIn("supervisor=supervise-daemon", getty.splitlines())
        self.assertIn("before docker", getty)
        self.assertIn("supervisor=supervise-daemon", docker.splitlines())
        self.assertNotIn("command_background=", docker)
        self.assertNotIn("sleep 0.5", docker)
        self.assertIn("--pidfile=/run/dockerd.pid", docker)
        self.assertIn('pidfile="/run/openrc/docker-supervise.pid"', docker)

    def test_login_and_docker_runtime_prerequisites_are_configured(self) -> None:
        getty = (
            ROOT / "components/system-core/rootfs/etc/init.d/getty-console"
        ).read_text()
        mdev = (ROOT / "components/system-core/rootfs/etc/init.d/mdev").read_text()
        scan = mdev.index("/sbin/mdev -s")
        self.assertIn("[ -w /proc/sys/kernel/hotplug ]", mdev)
        self.assertGreater(mdev.index("chmod 0666 /dev/null", scan), scan)

        for relative in (
            "components/system-core/rootfs/etc/skel/.zshrc",
            "components/system-core/rootfs/root/.zshrc",
            "components/openssh/rootfs/usr/libexec/strataos/firstboot",
        ):
            self.assertNotIn("ZSH_DISABLE_COMPFIX", (ROOT / relative).read_text())

        login_defs = (
            ROOT / "components/system-core/rootfs/etc/login.defs"
        ).read_text()
        expected_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        self.assertIn(f"ENV_PATH PATH={expected_path}", login_defs)
        self.assertIn(f'export PATH="{expected_path}"', (
            ROOT / "components/system-core/rootfs/etc/zshenv"
        ).read_text())
        self.assertIn("--sysconfdir=/etc", load_recipes()["shadow"].configure_args)

        zshrc = (ROOT / "components/system-core/rootfs/etc/zshrc").read_text()
        self.assertIn("stty erase '^?'", zshrc)
        self.assertIn("backward-delete-char", zshrc)
        self.assertIn("console vt100", getty)

        initial_setup = (
            ROOT / "components/system-core/rootfs/usr/libexec/strataos/initial-setup"
        ).read_text()
        self.assertIn("passwd root", initial_setup)
        self.assertIn("useradd -m -U", initial_setup)
        self.assertIn("wheel,audio,video,input,docker,netdev", initial_setup)

        ssh = (
            ROOT / "components/openssh/rootfs/etc/ssh/sshd_config.d/10-strataos.conf"
        ).read_text()
        self.assertIn("PermitRootLogin yes", ssh)
        self.assertIn("PasswordAuthentication yes", ssh)
        self.assertNotIn("authorized_keys", (ROOT / "scripts/image.py").read_text())

        system_core = load_data(ROOT / "components/system-core/component.conf")
        openssh = load_data(ROOT / "components/openssh/component.conf")
        python = load_data(ROOT / "components/python/component.conf")
        self.assertEqual("/var/lib/strataos/openssh", openssh["storage.0.mount"])
        self.assertEqual("system-core,network", openssh["requires"])
        self.assertEqual("system-core", python["requires"])
        self.assertEqual(["python"], (ROOT / "components/python/packages.list").read_text().splitlines())
        self.assertEqual(["openssh"], (ROOT / "components/openssh/packages.list").read_text().splitlines())
        self.assertEqual(["fail2ban"], (ROOT / "components/fail2ban/packages.list").read_text().splitlines())
        self.assertNotIn("openssh", (ROOT / "components/system-core/packages.list").read_text().splitlines())

        docker_sysctl = (
            ROOT / "components/docker/rootfs/etc/sysctl.d/90-docker.conf"
        ).read_text()
        self.assertIn("net.ipv4.ip_forward = 1", docker_sysctl)
        network_sysctl = (
            ROOT / "components/network/rootfs/etc/sysctl.d/50-network.conf"
        ).read_text()
        self.assertIn("net.ipv4.ping_group_range = 0 2147483647", network_sysctl)

        openrc_recipe = (ROOT / "packages/openrc/openrc.toml").read_text()
        openrc_patch = (
            ROOT / "packages/openrc/patches/openrc-cgroup-v2-explicit-pid.patch"
        ).read_text()
        self.assertIn("openrc-cgroup-v2-explicit-pid.patch", openrc_recipe)
        self.assertEqual(2, openrc_patch.count('printf \"%d\" \"$$\"'))

    def test_complete_commands_replace_busybox_links_without_runtime_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            output = Path(tmp_name)
            root = output / "component-root"
            (root / "bin").mkdir(parents=True)
            (root / "bin/busybox").write_text("busybox")
            (root / "bin/stat").symlink_to("busybox")
            (root / "bin/ping").symlink_to("busybox")
            (root / "sbin").mkdir()
            (root / "sbin/ip").symlink_to("../bin/busybox")
            (root / "usr/bin").mkdir(parents=True)
            (root / "usr/bin/passwd").symlink_to("../../bin/busybox")
            for package, relative in (
                ("coreutils", "usr/bin/stat"),
                ("iputils", "usr/bin/ping"),
                ("iproute2", "sbin/ip"),
                ("shadow", "usr/bin/passwd"),
            ):
                path = output / "packages" / package / "root" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative + "\n")
                merged = root / relative
                merged.parent.mkdir(parents=True, exist_ok=True)
                if not merged.exists() and not merged.is_symlink():
                    merged.write_text(relative + "\n")

            prefer_complete_commands(root, output)

            self.assertEqual("../usr/bin/stat", os.readlink(root / "bin/stat"))
            self.assertEqual("../usr/bin/ping", os.readlink(root / "bin/ping"))
            self.assertFalse((root / "sbin/ip").is_symlink())
            self.assertEqual("sbin/ip\n", (root / "sbin/ip").read_text())
            self.assertFalse((root / "usr/bin/passwd").is_symlink())
            self.assertEqual("usr/bin/passwd\n", (root / "usr/bin/passwd").read_text())
            verify_no_build_wrappers(root)


    def test_firewall_component_is_wired(self) -> None:
        self.assertEqual("1", self.x86["STRATA_ENABLE_FIREWALL"])
        self.assertEqual("1", self.arm["STRATA_ENABLE_FIREWALL"])

        fw = load_data(ROOT / "components/firewall/component.conf")
        self.assertEqual("firewall", fw["name"])
        self.assertEqual("system-core,network", fw["requires"])
        self.assertEqual("strataos-firewall", fw["services"])
        self.assertEqual("0", fw["storage.count"])

        fw_packages = (ROOT / "components/firewall/packages.list").read_text()
        core_packages = (ROOT / "components/system-core/packages.list").read_text().splitlines()
        for pkg in ("nftables", "libnftnl"):
            self.assertNotIn(pkg, core_packages)
            self.assertIn(f"\n{pkg}\n", f"\n{fw_packages}\n")
        for pkg in ("gmp", "readline", "libmnl"):
            self.assertIn(pkg, core_packages)

        init = (ROOT / "components/firewall/rootfs/etc/init.d/strataos-firewall").read_text()
        self.assertIn("before docker", init)
        self.assertIn("nft -f", init)

        common = (ROOT / "components/firewall/rootfs/usr/libexec/strataos/firewall-common").read_text()
        self.assertIn("fw_deny_blocks_protected", common)
        self.assertIn("fw_protected_ports", common)
        self.assertIn("22", common)
        self.assertIn("FW_ROLLBACK_DEADLINE", common)
        self.assertIn('rm -f "$FW_CANDIDATE"', common)


    def test_development_config_scripts_are_not_shipped_at_runtime(self) -> None:
        self.assertFalse(runtime_path("usr/bin/curl-config", Path("curl-config")))
        self.assertFalse(runtime_path("usr/bin/gpgrt-config", Path("gpgrt-config")))
        self.assertTrue(runtime_path("usr/bin/gpgconf", Path("gpgconf")))

    def test_shutdown_aliases_are_native_and_build_wrappers_are_not_shipped(self) -> None:
        openrc_recipe = (ROOT / "packages/openrc/openrc.toml").read_text()
        shutdown_patch = (
            ROOT / "packages/openrc/patches/openrc-shutdown-command-aliases.patch"
        ).read_text()
        self.assertIn("openrc-shutdown-command-aliases.patch", openrc_recipe)
        for name in ("halt", "poweroff", "reboot", "shutdown"):
            self.assertIn(f'"{name}"', shutdown_patch)
            self.assertFalse(
                (ROOT / "components/system-core/rootfs/usr/local/sbin" / name).exists()
            )

        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            (root / "usr/bin").mkdir(parents=True)
            (root / "usr/bin/run-target").write_text("#!/bin/sh\n")
            with self.assertRaises(BuildError):
                verify_no_build_wrappers(root)

    def test_default_storage_is_nonredundant_and_sparse(self) -> None:
        storage = load_data(ROOT / "configs/runtime/storage.conf")
        self.assertEqual("none", storage["volume.default.redundancy"])
        self.assertEqual("no", storage["volume.default.preallocate"])
        self.assertEqual("crc32c", storage["volume.default.integrity"])

    def test_component_update_preflights_dependencies_and_verification(self) -> None:
        updater = (ROOT / "components/system-core/rootfs/usr/libexec/strataos/componentctl").read_text()
        self.assertIn('[ "$architectures" = "$machine" ]', updater)
        self.assertIn("component priority $priority is already used", updater)
        self.assertIn("requires missing component", updater)
        self.assertIn("verify_active()", updater)
        self.assertNotIn("active_list | while", updater)

    def test_component_version_catalog_describes_artifacts_and_storage_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            output = Path(tmp_name)
            artifact = output / "components" / "system-core-test.squashfs"
            artifact.parent.mkdir()
            artifact.write_bytes(b"component artifact\n")
            slot = output / "slot-A/components.list"
            slot.parent.mkdir()
            slot.write_text("components/system-core-test.squashfs\n")

            catalog = write_component_versions(
                self.x86, output, {"system-core": artifact}, slot
            )
            document = json.loads(catalog.read_text())

            self.assertEqual(1, document["format"])
            self.assertEqual(
                {"version": self.x86["STRATA_VERSION"], "architecture": "x86_64"},
                document["release"],
            )
            entry = document["components"][0]
            self.assertEqual("system-core", entry["name"])
            self.assertEqual("components/system-core-test.squashfs", entry["artifact"]["path"])
            self.assertEqual(sha256_file(artifact), entry["artifact"]["sha256"])
            self.assertEqual(
                [{"id": "state", "schema": 1, "lifecycle": "retain"}],
                entry["storage"],
            )
            self.assertEqual(
                sha256_file(catalog),
                catalog.with_suffix(".json.sha256").read_text().split()[0],
            )

    def test_no_shipped_data_images(self) -> None:
        self.assertEqual([], [path for path in ROOT.rglob("*.ext4") if "output" not in path.parts])
        self.assertEqual([], [path for path in ROOT.rglob("*.img") if "output" not in path.parts])

    def test_no_external_backend_tree_or_symbols(self) -> None:
        token = "build" + "root"
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or "output" in path.parts
                or "__pycache__" in path.parts
                or path.suffix in {".pyc", ".pyo"}
            ):
                continue
            self.assertNotIn(token, path.read_text(errors="ignore").lower(), str(path))

    def test_python_and_openssh_are_separate_components_with_coordinated_dependencies(self) -> None:
        recipes = load_recipes()
        self.assertEqual(("python", "nftables"), recipes["fail2ban"].dependencies)
        self.assertIn("host-python", recipes["python"].dependencies)
        self.assertIn("sqlite", recipes["python"].dependencies)
        core = (ROOT / "components/system-core/packages.list").read_text().splitlines()
        self.assertNotIn("python", core)
        self.assertNotIn("openssh", core)
        self.assertNotIn("fail2ban", core)
        self.assertIn("sqlite", core)
        self.assertEqual("sshd", load_data(ROOT / "components/openssh/component.conf")["services"])
        fail2ban = load_data(ROOT / "components/fail2ban/component.conf")
        self.assertEqual("fail2ban", fail2ban["services"])
        self.assertEqual("system-core,network,python,openssh,firewall", fail2ban["requires"])

    def test_arm64_and_x86_share_network_kernel_requirements(self) -> None:
        required = {
            line.split()[0] for line in (ROOT / "configs/kernel/required-symbols.list").read_text().splitlines()
            if line and not line.startswith("#")
        }
        expected = {"CONFIG_NF_TABLES_INET", "CONFIG_NFT_REJECT_INET", "CONFIG_VLAN_8021Q", "CONFIG_PPPOE"}
        self.assertTrue(expected.issubset(required))
        for arch in ("x86_64", "arm64"):
            body = (ROOT / f"configs/kernel/{arch}/kernel.config").read_text()
            for symbol in expected:
                self.assertIn(f"{symbol}=y", body)

    def test_optional_application_components_are_selected_independently(self) -> None:
        config = dict(self.x86)
        config.update({
            "STRATA_ENABLE_DOCKER": "0",
            "STRATA_ENABLE_GRAPHICS": "0",
            "STRATA_ENABLE_CJK_FONTS": "0",
        })
        packages = component_package_names(config)
        self.assertNotIn("docker-static", packages)
        self.assertNotIn("cage", packages)
        self.assertNotIn("noto-sans-cjk-sc", packages)



if __name__ == "__main__":
    unittest.main()
