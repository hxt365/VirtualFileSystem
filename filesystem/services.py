import json

import redis
from decouple import config

r = redis.StrictRedis(host=config('REDIS_HOST'), port=config('REDIS_PORT'), password=config('REDIS_PASSWORD'),
                      db=0, decode_responses=True)

"""
File system is stored in Redis with structure:
root = id
file-id:children = set{child_1_id, child_2_id, ...}
file-id:data = file
file = json{id, name, created_at, updated_at, size, data, is_folder, parent_id, _size}
"""


def get_root_id():
    id = r.get('root_id')
    if id:
        return int(id)
    return None


def get_root_data():
    """
    Return root directory instance.
    """
    root_id = get_root_id()
    if root_id:
        return get_data(file_id=root_id)
    return None


def set_root_data(root_file):
    """
    Add root directory to cache.
    """
    r.set('root_id', root_file.id)
    r.set('{}:data'.format(root_file.id), root_file.to_json())


def set_data(file):
    """
    Add file data to cache.
    """
    r.set('{}:data'.format(file.id), file.to_json())


def get_data(file_id):
    """
    Get file instsance by its id from cache.
    """
    dump = r.get('{}:data'.format(file_id))
    data = json.loads(dump)
    return data


def get_children(folder_id):
    """
    Get all children within a folder from cache.
    """
    children_ids = r.smembers('{}:children'.format(folder_id))
    return [get_data(id) for id in children_ids]


def set_children(folder_id, children):
    """
    Set children for a folder in cache.
    """
    for child in children:
        r.sadd('{}:children'.format(folder_id), child.id)


def add_child(folder, file):
    """
    Add a child item into a folder.
    """
    r.sadd('{}:children'.format(folder.id), file.id)
    set_data(file)
    if file.is_folder:
        set_data(folder)  # update updated_at
    else:
        bubble_delete(folder.id, root_id=get_root_id())  # invalidate cache as size may change


def rm_child(folder_id, file_id):
    """
    Delete a file_id from folder:children, that file is a child of the folder.
    We also need to remove the file from cache to reclaim memory.
    """
    r.srem('{}:children'.format(folder_id), file_id)
    bubble_delete(file_id, root_id=get_root_id())  # invalidate cache as size may change
    # here we can also delete files down the file system tree from the file being deleted


def bubble_delete(file_id, root_id):
    """
    Delete file's parent, grandparent, grand grandparent, ... (bottom up) except root directory.
    """
    if file_id == root_id:
        return
    parent_id = get_data(file_id=file_id).get('parent_id')
    r.delete(parent_id)
    bubble_delete(file_id=parent_id, root_id=root_id)
