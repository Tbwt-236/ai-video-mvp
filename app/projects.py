"""Independent project copies with atomic database insertion and rollback."""
import copy
import shutil
from uuid import uuid4

from .store import now


def copy_projects(store, original, changes=None, aspects=None):
    base=copy.deepcopy(original)
    base.update(changes or {})
    group=str(uuid4())
    projects=[]
    for aspect in aspects or [None]:
        project=copy.deepcopy(base)
        suffix=f" · {aspect}" if aspect else " · 副本"
        project.update(id=str(uuid4()),title=base["title"][:32-len(suffix)]+suffix,version=1,
                       duration=sum(scene["duration"] for scene in project["scenes"]),
                       archived=False,created_at=now(),updated_at=now())
        if aspect:
            project.update(aspect=aspect,variant_of=original["id"],variant_group=group)
        projects.append(project)
    source=store.directory/"assets"/original["id"]
    try:
        for project in projects:
            destination=store.directory/"assets"/project["id"]
            if source.is_dir():
                shutil.copytree(source,destination)
        store.insert_projects(projects)
    except Exception:
        for project in projects:
            shutil.rmtree(store.directory/"assets"/project["id"],ignore_errors=True)
        raise
    return projects
