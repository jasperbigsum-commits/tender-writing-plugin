"""Validate the authored package and create a reproducible, single-plugin ZIP."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "tender-writing"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def frontmatter(text):
    # Authoring intentionally uses the JSON-string subset of YAML scalars.
    # Parse values as data, reject duplicate keys and unsupported YAML syntax.
    assert text.startswith("---\n"), "missing YAML frontmatter"
    header = text.split("---\n", 2)[1]
    data = {}
    for line in header.splitlines():
        key, value = line.split(":", 1)
        assert key not in data, "duplicate YAML key"
        data[key] = json.loads(value.strip())
    assert set(data) == {"name", "description"}
    assert all(isinstance(value, str) and value.strip() for value in data.values())
    return data


def main():
    manifest = load(PLUGIN / "plugin.json")
    name, version = manifest["name"], manifest["version"]
    assert name == PLUGIN.name and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
    assert len(name) <= 64 and re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert not set(manifest) & {"skills", "mcpServers", "apps", "interface"}
    interface = manifest["extensions"]["com.openai"]["interface"]
    assert 0 < len(interface["shortDescription"]) <= 30
    assert interface["category"] == "Business & Operations"
    assert isinstance(interface["capabilities"], list)
    assert 1 <= len(interface["defaultPrompt"]) <= 3
    assert all(isinstance(p, str) and 0 < len(p) <= 128 for p in interface["defaultPrompt"])
    for asset in ("logo", "composerIcon"):
        assert (PLUGIN / interface[asset]).resolve().is_relative_to(PLUGIN.resolve())
        assert (PLUGIN / interface[asset]).is_file()
    for compat in (".codex-plugin", ".claude-plugin"):
        data = load(PLUGIN / compat / "plugin.json")
        assert data["name"] == name and data["version"] == version
        if compat == ".codex-plugin":
            assert data["interface"]["category"] == interface["category"]
            assert data["interface"]["shortDescription"] == interface["shortDescription"]
            assert data["interface"]["defaultPrompt"] == interface["defaultPrompt"]
    skills = []
    for path in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        assert path.stat().st_size <= 1024 * 1024
        data = frontmatter(text)
        assert data["name"] == path.parent.name
        assert data["name"] not in skills
        skills.append(data["name"])
        # JSON is a valid YAML document; this parses the complete authored agent YAML.
        agent = load(path.parent / "agents/openai.yaml")
        assert agent["interface"]["display_name"].strip()
        assert agent["interface"]["short_description"].strip()
        assert isinstance(agent["interface"]["default_prompt"], str)
        assert isinstance(agent["policy"]["allow_implicit_invocation"], bool)
        assert set(agent["policy"]) <= {"products", "allow_implicit_invocation"}
    assert len(skills) == 6
    files = []
    for path in sorted(PLUGIN.rglob("*")):
        assert not path.is_symlink(), f"symlink: {path}"
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
            continue
        relative = path.relative_to(PLUGIN)
        assert path.name not in (".env", "config.json", "auth.json")
        assert not set(relative.parts) & {"node_modules", ".venv", ".git", "outputs", "projects"}
        if path.suffix == ".json":
            load(path)
        if path.suffix == ".md":
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+://|#", link):
                    continue
                target = (path.parent / link.split("#", 1)[0]).resolve()
                assert target.is_relative_to(PLUGIN.resolve()), f"outside link: {path}: {link}"
                assert target.is_file(), f"broken link: {path}: {link}"
        files.append(path)
    catalog = load(ROOT / ".claude-plugin/marketplace.json")
    entry = catalog["plugins"][0]
    assert entry["name"] == name and entry["source"]["path"] == f"./{name}"
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / f"{name}-{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as stream:
        for path in files:
            info = zipfile.ZipInfo(f"{name}/{path.relative_to(PLUGIN).as_posix()}", date_time=(2026, 11, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            stream.writestr(info, path.read_bytes())
    # Verify the actual bytes being delivered, including hidden manifests.
    with zipfile.ZipFile(archive) as stream:
        assert stream.testzip() is None
        names = stream.namelist()
        assert len(names) == len(files) and len(set(names)) == len(names)
        assert {n.split("/")[0] for n in names} == {name}
        assert all(".." not in Path(n).parts and "\\" not in n for n in names)
        saved = json.loads(stream.read(f"{name}/plugin.json"))
        assert saved == manifest
        for skill in skills:
            frontmatter(stream.read(f"{name}/skills/{skill}/SKILL.md").decode("utf-8"))
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / f"{name}-{version}.sha256").write_text(f"{sha}  {archive.name}\n", encoding="ascii")
    result = {"archive": archive.relative_to(ROOT).as_posix(), "sha256": sha, "version": version, "skills": skills,
              "files": len(files), "bytes": archive.stat().st_size,
              "subtitle_characters": len(interface["shortDescription"]), "validation": "passed",
              "host_installation": "not_performed"}
    (destination / "package-validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
