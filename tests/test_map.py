import pytest
from chronicler.storage.map import MapManager

@pytest.fixture
def map_dir(tmp_path):
    d = tmp_path / ".chronicler"
    d.mkdir()
    return d

def test_create_initial_map(map_dir):
    mgr = MapManager(str(map_dir))
    mgr.create_initial(project_name="my-app", framework="nextjs", languages=["typescript"])
    content = (map_dir / "CHRONICLER_MAP.md").read_text()
    assert "my-app" in content
    assert "nextjs" in content

def test_read_returns_content(map_dir):
    mgr = MapManager(str(map_dir))
    mgr.create_initial(project_name="test", framework=None, languages=["python"])
    assert "Chronicler Map" in mgr.read()

def test_read_missing_returns_empty(map_dir):
    mgr = MapManager(str(map_dir))
    assert mgr.read() == ""

def test_update_dependencies(map_dir):
    mgr = MapManager(str(map_dir))
    mgr.create_initial(project_name="test", framework=None, languages=["python"])
    mgr.update({"dependencies": ["requests: 2.31.0"], "features": None,
                 "routes": None, "known_issues": None})
    assert "requests" in mgr.read()
