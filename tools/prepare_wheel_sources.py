"""Select and verify platform artifacts from the frozen uv lock, without re-resolving."""

import hashlib
import sys
import tomllib
import urllib.request
from pathlib import Path

from pip._vendor.packaging.markers import Marker
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import parse_wheel_filename

lock = tomllib.loads(Path(sys.argv[1]).read_text())
dest = Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)
tags = list(sys_tags())
rank = {tag: i for i, tag in enumerate(tags)}
selected = []
for package in lock["package"]:
    if "registry" not in package.get("source", {}):
        continue
    markers = package.get("resolution-markers", [])
    if markers and not any(Marker(marker).evaluate() for marker in markers):
        continue
    choices = []
    for wheel in package.get("wheels", []):
        filename = wheel["url"].rsplit("/", 1)[-1]
        supported = parse_wheel_filename(filename)[3] & set(tags)
        if supported:
            choices.append((min(rank[t] for t in supported), wheel))
    artifact = min(choices, key=lambda c: c[0])[1] if choices else package.get("sdist")
    if artifact is None:
        raise RuntimeError("no build artifact: " + package["name"])
    name = artifact["url"].rsplit("/", 1)[-1]
    target = dest / name
    raw = urllib.request.urlopen(artifact["url"]).read()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != artifact["hash"]:
        raise RuntimeError("artifact digest mismatch: " + name)
    target.write_bytes(raw)
    selected.append(str(target))
    print(package["name"], name, flush=True)
(dest / "sources.txt").write_text("\n".join(selected) + "\n")
