from pathlib import Path

from app.config import Settings


def test_material_directory_follows_runtime_data_directory(tmp_path: Path) -> None:
    runtime_data = tmp_path / "runtime"
    settings = Settings(_env_file=None, runtime_data_dir=runtime_data)

    assert settings.material_dir == runtime_data / "materials"
