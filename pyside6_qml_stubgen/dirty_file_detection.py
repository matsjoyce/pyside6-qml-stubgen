import dataclasses
import pathlib
import sys
import typing

import pydantic

from . import _version


@dataclasses.dataclass
class PythonModuleMetadata:
    modification_time: float
    path: pathlib.Path
    dependencies: typing.Sequence[str]


@dataclasses.dataclass
class PythonModulesMetadata:
    modules: typing.Mapping[str, PythonModuleMetadata | None]
    generating_version: str = ""


PYTHON_MODULES_METADATA_TYPE_ADAPTER = pydantic.TypeAdapter(PythonModulesMetadata)


def load_modules_metadata(dir_path: pathlib.Path) -> PythonModulesMetadata:
    if (dir_path / "metadata.json").exists():
        metadata = PYTHON_MODULES_METADATA_TYPE_ADAPTER.validate_json(
            (dir_path / "metadata.json").read_bytes()
        )
        if metadata.generating_version == _version.__version__:
            return metadata
    return PythonModulesMetadata({})


def save_modules_metadata(
    dir_path: pathlib.Path, metadata: PythonModulesMetadata
) -> None:
    with open(dir_path / "metadata.json", "wb") as f:
        f.write(PYTHON_MODULES_METADATA_TYPE_ADAPTER.dump_json(metadata, indent=4))


def recursive_module_metadata_addition(
    module_name: str,
    dependency_map: typing.Mapping[str, set[str]],
    module_metadata: dict[str, PythonModuleMetadata | None],
) -> None:
    if module_name in module_metadata:
        return
    if module_name not in sys.modules:
        module_metadata[module_name] = None
        return
    mod = sys.modules[module_name]
    fname: str | None = getattr(mod, "__file__", None)
    if fname is None or not pathlib.Path(fname).exists():
        module_metadata[module_name] = None
        return
    deps = dependency_map.get(module_name, set())
    module_metadata[module_name] = PythonModuleMetadata(
        modification_time=pathlib.Path(fname).stat().st_mtime,
        path=pathlib.Path(fname),
        dependencies=sorted(deps),
    )
    for dep in deps:
        recursive_module_metadata_addition(dep, dependency_map, module_metadata)


def imported_files() -> set[pathlib.Path]:
    files = set()
    for mod in sys.modules.values():
        fname: str | None = getattr(mod, "__file__", None)
        if fname is not None and pathlib.Path(fname).exists():
            files.add(pathlib.Path(fname))
    return files


def detect_new_and_dirty_files(
    current_files: typing.Sequence[pathlib.Path],
    modules_metadata: PythonModulesMetadata,
) -> tuple[
    dict[pathlib.Path, str], dict[str, PythonModuleMetadata | None], set[pathlib.Path]
]:
    # Perform a Bellman-Ford-style search (due to possible import cycles) to find out the full
    # set of paths that should be considered dirty (and why)
    # module_dirty is a dict of module name to dirty dependency (or None if it is not dirty)
    module_dirty: dict[str, str | None] = {}

    # Initialise to whether the particular file has changed
    for name, meta in modules_metadata.modules.items():
        if meta is not None and (
            not meta.path.exists()
            or meta.modification_time != meta.path.stat().st_mtime
        ):
            # Changed
            module_dirty[name] = name
        else:
            module_dirty[name] = None

    # Propagate changes until no more changes are made
    found_change = True
    while found_change:
        found_change = False
        for name, meta in modules_metadata.modules.items():
            if module_dirty[name] is None and meta is not None:
                for dep in meta.dependencies:
                    if module_dirty[dep]:
                        module_dirty[name] = module_dirty[dep]
                        found_change = True
                        break

    # Calculate reachable modules from the current set of files (so that we can discard the rest)
    module_path_to_name = {
        meta.path: name
        for name, meta in modules_metadata.modules.items()
        if meta is not None
    }
    reachable_modules = {
        maybe_name
        for cf in current_files
        if (maybe_name := module_path_to_name.get(cf))
    }

    previous_reachable_modules: set[str] = set()
    while reachable_modules != previous_reachable_modules:
        previous_reachable_modules = reachable_modules.copy()
        for name in previous_reachable_modules:
            if meta := modules_metadata.modules[name]:
                reachable_modules.update(meta.dependencies)

    # And construct the final output
    dirty_files = {
        cf: (
            "new"
            if module_name is None
            else (
                "changed"
                if dirty_dep == module_name
                else f"dependency {dirty_dep} changed"
            )
        )
        for cf in current_files
        if (module_name := module_path_to_name.get(cf)) is None
        or (dirty_dep := module_dirty[module_name])
    }
    cleaned_modules_metadata = {
        name: meta
        for name, meta in modules_metadata.modules.items()
        if name in reachable_modules and module_dirty[name] is None
    }
    return (
        dirty_files,
        cleaned_modules_metadata,
        {
            meta.path
            for name, reason in module_dirty.items()
            if reason is not None and (meta := modules_metadata.modules[name])
        },
    )
