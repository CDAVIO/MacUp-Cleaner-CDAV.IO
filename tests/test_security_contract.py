import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent / "engine"
SCRIPT = REPO / "clean_mac.sh"
SHELL_SOURCES = [SCRIPT, *sorted((REPO / "lib").rglob("*.sh"))]


def _owning_shell_function(lines, index):
    function = "<top-level>"
    declaration = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(\) \{")
    for line in lines[: index + 1]:
        match = declaration.match(line)
        if match:
            function = match.group(1)
    return function


def test_recursive_rm_is_confined_to_shared_removal_helpers():
    allowed = {"safe_rm", "safe_rm_contents"}
    violations = []
    for source_path in SHELL_SOURCES:
        lines = source_path.read_text().splitlines()
        for index, line in enumerate(lines):
            code = line.split("#", 1)[0]
            if re.search(r"(?:^|\s)(?:sudo\s+)?rm\s+-[A-Za-z]*r[A-Za-z]*f?\s", code):
                owner = _owning_shell_function(lines, index)
                if owner not in allowed:
                    violations.append(
                        (str(source_path.relative_to(REPO)), index + 1, owner, line.strip())
                    )
    assert violations == []


def test_path_policy_has_single_module_definition():
    main_source = SCRIPT.read_text()
    executor_source = (REPO / "lib/core/executor.sh").read_text()
    module_source = (REPO / "lib/core/path_policy.sh").read_text()
    assert 'source "$SCRIPT_DIR/lib/core/executor.sh"' in main_source
    assert 'source "$SCRIPT_DIR/lib/core/path_policy.sh"' in executor_source
    assert "_validate_removal_path()" not in main_source
    assert module_source.count("_validate_removal_path()") == 1


def test_executor_has_single_mutation_sink_definition():
    main_source = SCRIPT.read_text()
    executor_source = (REPO / "lib/core/executor.sh").read_text()
    assert "safe_rm()" not in main_source
    assert executor_source.count("safe_rm()") == 1
    assert executor_source.count("safe_rm_contents()") == 1


def test_project_artifacts_have_single_domain_module_definition():
    main_source = SCRIPT.read_text()
    module_source = (REPO / "lib/categories/project_artifacts.sh").read_text()
    assert 'source "$SCRIPT_DIR/lib/categories/project_artifacts.sh"' in main_source
    assert "clean_project_artifacts()" not in main_source
    assert module_source.count("clean_project_artifacts()") == 1


def test_installer_artifacts_have_single_domain_module_definition():
    main_source = SCRIPT.read_text()
    module_source = (REPO / "lib/categories/installer_artifacts.sh").read_text()
    assert 'source "$SCRIPT_DIR/lib/categories/installer_artifacts.sh"' in main_source
    assert "clean_installer_artifacts()" not in main_source
    assert module_source.count("clean_installer_artifacts()") == 1
    assert "is_orphaned\\\": false" in module_source


def test_app_uninstaller_has_single_domain_module_definition():
    main_source = SCRIPT.read_text()
    module_source = (REPO / "lib/categories/app_uninstaller.sh").read_text()
    assert 'source "$SCRIPT_DIR/lib/categories/app_uninstaller.sh"' in main_source
    for function in (
        "scan_app_uninstaller",
        "clean_app_uninstaller",
        "get_app_bundle_id",
        "is_valid_app_bundle_path",
        "app_leftover_paths",
        "scan_app_uninstaller_subitems_json",
    ):
        assert f"{function}()" not in main_source
        assert module_source.count(f"{function}()") == 1


def test_mutating_owner_commands_use_the_dry_run_gateway():
    source = "\n".join(path.read_text() for path in SHELL_SOURCES)
    patterns = (
        r"run_mutating_action docker_cleaned docker_cleanup_failed\s+\\?\s*docker system prune -a -f --volumes",
        r"run_mutating_action brew_cleanup_success brew_cleanup_failed\s+\\?\s*brew cleanup -s",
        r"run_mutating_action simctl_deleted simctl_failed\s+\\?\s*xcrun simctl delete unavailable",
        r"run_mutating_action ql_reset ql_failed qlmanage -r cache",
    )
    for pattern in patterns:
        assert re.search(pattern, source), pattern


def test_terminal_tool_never_clears_quarantine_or_uses_sudo():
    root = REPO.parent
    sources = [root / "macup", root / "install.sh", *sorted((root / "lib").glob("*.sh"))]
    for source_path in sources:
        code = "\n".join(line.split("#", 1)[0] for line in source_path.read_text().splitlines())
        assert "xattr -d" not in code, source_path
        assert "xattr -r" not in code, source_path
        assert not re.search(r"(^|[\s;(|&])sudo\s", code), source_path


def test_terminal_tool_always_runs_the_engine_in_trash_only_mode():
    root = REPO.parent
    clean = (root / "lib" / "clean.sh").read_text()
    calls = []
    for source_path in [root / "macup", *sorted((root / "lib").glob("*.sh"))]:
        for line in source_path.read_text().splitlines():
            if "clean_mac.sh" in line.split("#", 1)[0]:
                calls.append((source_path.name, line.strip()))
    assert calls, "engine call not found"
    body = clean[clean.index("engine() {"):clean.index("}", clean.index("engine() {"))]
    assert "APPLE_CLEANUP_TRASH_ONLY=1" in body
    assert "APPLE_CLEANUP_FORCE_MANUAL_TRASH=1" in body
    assert "FORCE_RM=0 TEST_MODE=0" in body
    # Only engine() may start the engine.
    assert len(calls) == 1


def test_developer_cleanup_offers_only_rebuildable_caches():
    clean = (REPO.parent / "lib" / "clean.sh").read_text()
    safe = set(re.search(r'^CLEAN_DEV_SAFE="([^"]*)"', clean, re.M).group(1).split())
    valid = set(re.search(r'^_VALID_DEVELOPER_KEYS="([^"]*)"', SCRIPT.read_text(), re.M).group(1).split("|"))
    assert safe and safe <= valid
    never = {
        "docker_prune", "simctl_unavailable", "simulator_devices", "brew_cleanup",  # delete for good
        "ollama_models", "lm_studio", "huggingface_cache",  # downloaded AI models
        "xcode_archives", "broken_links", "font_caches", "maven_repo", "flutter_pub_cache",
    }
    assert safe & never == set()
    # Every offered item must be cleaned through the Trash-only helper.
    engine = SCRIPT.read_text()
    for item in safe:
        branch = re.search(rf"^\s+{item}\)\n(.*?)\n\s+;;", engine, re.M | re.S)
        assert branch, item
        assert "safe_rm_contents" in branch.group(1), item
        assert "run_mutating_action" not in branch.group(1), item
