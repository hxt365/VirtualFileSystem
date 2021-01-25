import json
from typing import Dict, Any, List

import redis
from decouple import config
from django.apps import apps

File = apps.get_model(app_label='filesystem', model_name='File')

r = redis.Redis(host=config('REDIS_HOST'), port=config('REDIS_PORT'), db=0)


def get_root() -> Dict[str, Any]:
    """
    Get value of root directory from Redis.
    """
    json_dump = r.get('/')
    return File(**json.loads(json_dump))


def set_root(root: File) -> None:
    """
    Create root directory in Redis.
    """
    r.set('/', json.dumps(root))


def set_file(file: File) -> None:
    """
    Set a file in Redis.
    """
    r.set(file.id, json.dumps(file))


def get_children(folder: File) -> List[Dict[str, Any]]:
    """
    Get values of all children within a folder from Redis.
    """
    json_dump = r.smembers('{}:children'.format(folder.id))
    return [File(**kwargs) for kwargs in json.loads(json_dump)]


def add_child(folder: File, child: File) -> None:
    """
    Add a child into a folder in Redis.
    Call after update instances.
    """
    r.sadd('{}:children'.format(folder.id), json.dumps(child))
    r.set(folder.id, json.dumps(folder))  # update updated_at


def rm_child(folder: File, child: File) -> None:
    """
    Delete a child within a folder.
    Call after update folder, before  delete child.
    """
    r.srem('{}:children'.format(folder.id), json.dumps(child))
    r.set(folder.id, json.dumps(folder))  # update updated_at


def get_file(id: int) -> File:
    """
    Get a file from Redis by its id.
    """
    return File(**json.loads(r.get(id)))


def bulble_delete(file: File) -> None:
    """
    Delete a file and its parent, grandparent,... (bottom-up) in Redis.
    """
    parent = get_file(file.parent_id)
    while parent.name != '/':
        grand_parrent = get_file(parent.id)
        rm_child(grand_parrent, parent)
        parent = grand_parrent
