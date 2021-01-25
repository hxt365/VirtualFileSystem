from queue import SimpleQueue
from typing import AnyStr, List

from django.db import transaction

from filesystem import services as cache
from .exceptions import FileNotFound, FileExisted, ForbiddenOperation, MovedIntoSubFolder
from .models import FilePath, File, dict_to_file


def _get_root_directory() -> File:
    """
    This method allows us to retrieve the root directory.
    If it does not exist, then the reason must be that the database has just been newly created, so create a new one.
    :return: a file instance of root directory.
    """
    # Transaction with serializable isolation level guarantees that there will be no race condition, that means that
    # there will be only one root directory created.
    with transaction.atomic(using='serializable'):
        try:
            root = dict_to_file(cache.get_root_data())
            if root:
                return root
            root = File.objects.get(name='/')
            cache.set_root_data(root)
        except File.DoesNotExist:
            root = File.objects.create(name='/', is_folder=True)
            cache.set_root_data(root)
        return root


def get_file(filepath: FilePath) -> File:
    """
    This method allows us to retrieve the file instance based on its filepath.
    :param filepath: a normalized filepath.
    :return: a desired file instance.
    :exception FileNotFound: raised when no file or directory match the filepath.
    """
    current_file = _get_root_directory()
    filenames = filepath.dirs()  # Normalize and extract filenames from the filepath
    # Traverse the filepath
    for filename in filenames:
        try:
            current_file = current_file.get_child(filename)
        except (File.DoesNotExist, ForbiddenOperation):
            raise FileNotFound
    return current_file


def create_file(filepath: FilePath, p_flag: bool = False, data: AnyStr = None) -> File:
    """
    This method allows us to create a new file at filepath.
    This method is atomic.
    :param filepath: a normalized filepath.
    :param data: content of the file. If data is None, then the file is a folder.
    :param p_flag: If p_flag is True, then create the missing parent folders if needed. Otherwise, raise error.
    :return: A newly created file.
    :exception FileNotFound: raised if the parent folders are missing.
    :exception FileExisted: raised if the filename is duplicated.
    """
    if filepath.path == '/':
        raise FileExisted
    # Create new file
    filename = filepath.dirs()[-1]
    new_file = File(name=filename, data=data, is_folder=data is None)
    if not p_flag:
        # We need a transaction here to avoid concurrent transaction deleting parent folder right before we add the
        # child to it
        with transaction.atomic():
            parent_folder = get_file(filepath=filepath.parent())
            parent_folder.add_child(new_file)
    else:
        current_file = _get_root_directory()
        # Traverse the parent folder's filepath
        filenames = filepath.parent().dirs()
        # We need a transaction here to avoid concurrent transaction deleting parent folder right before we add the
        # child to it
        with transaction.atomic():
            for filename in filenames:
                # Create folder if it does not exist
                try:
                    current_file = current_file.get_child(filename)
                except FileNotFound:
                    tmp_file = File(name=filename, is_folder=True)
                    current_file.add_child(tmp_file)
                    current_file = tmp_file
                except ForbiddenOperation:
                    raise FileNotFound
            current_file.add_child(new_file)
    return new_file


def update_file(filepath: FilePath, new_name: AnyStr, new_data: AnyStr = None) -> File:
    """
    This method allows us to update an existing file at filepath.
    This method is atomic.
    :param filepath: a normalized filepath.
    :param new_name: a new name to be updated to
    :param new_data: new content to be updated.
    If data is None, then no need to update. If the file is a folder, just ignore the data.
    :return: The updated file.
    :exception FileNotFound: raised if the parent folders are missing.
    """
    file = get_file(filepath)
    file.name = new_name
    if not file.is_folder and new_data:
        file.data = new_data
    file.save()
    return file


def remove_file(filepaths: List[FilePath]) -> None:
    """
    This method allows us to delete files, that exist at filepath in the list of filepaths.
    This method is not fully atomic, but it guarantees that each deletion of a filepath is atomic.
    :param filepaths: list of normalized filepaths.
    :exception FileNotFound: raised if the file at filepath does not exist.
    Method will stop immediately when it encounters an exception.
    """
    for filepath in filepaths:
        parent_filepath = filepath.parent()
        filename = filepath.dirs()[-1]
        with transaction.atomic():
            parent_folder = get_file(parent_filepath)
            parent_folder.remove_child(filename)


def move_file(filepath: FilePath, folder_path: FilePath) -> None:
    """
    Move a file into the destination folder_path.
    :param filepath: the normalized filepath of the file being  moved.
    :param folder_path: a normalized filepath of the destination folder.
    :exception FileNotFound raised when the the file being moved or the folder does not exist, or the file at the
    folder_path is a normal file.
    :exception MoveIntoSubFolder raised when the folder_path is sub-path of filepath.
    """
    if folder_path.path.startswith(filepath.path):
        raise MovedIntoSubFolder
    # Transaction is needed to provide atomicity and guarantee file and folder are not deleted by concurrent transaction
    # during moving
    with transaction.atomic():
        file = get_file(filepath)
        folder = get_file(folder_path)
        if not folder.is_folder:
            raise FileNotFound
        folder.add_child(file)


def find(name: AnyStr, folder_path: FilePath = FilePath('/'), max_level: int = 10) -> List[AnyStr]:
    """
    Search all files/folders within folder_path, whose name contains exactly the substring NAME.
    :param name: a string that filenames must contain. If name is blank, return all files within the folder.
    :param folder_path: the path of folder that we search in
    :param max_level: an integer, which indicates how many levels we can traverse down the file tree to search. This is
    important to find a reasonable value, because the find method uses transaction to ensure files are not deleted by
    concurrent transaction, which can cause errors during searching, hence performance is downgraded.
    :return: an alphabetically sorted list of filenames, or an empty list if there are no results.
    :exception FileNotFound: raised if the folder at folder_path is a normal file
    Note: root cannot be search.
    """
    with transaction.atomic():
        folder = get_file(folder_path)
        if not folder.is_folder:
            raise FileNotFound
        # Traverse down the file "tree" and search for NAME
        results = []
        # Implementation uses breadth-first search (BFS) technique
        folders = SimpleQueue()
        # A queue used for BFS, each item in folders contains a current folder instance, a current filepath, and a
        # current level
        folders.put(
            (folder, folder_path.path.rstrip('/'), 0))  # For special case when search in root folder
        while not folders.empty():
            cur_folder, cur_path, cur_level = folders.get()
            if cur_level == max_level:
                continue
            for child in cur_folder.get_children():
                filepath = '{}/{}'.format(cur_path, child.name)
                if name in child.name:
                    results.append('{}{}'.format(filepath, '/' if child.is_folder else ''))  # add trailing slash
                if child.is_folder:
                    folders.put((child, filepath, cur_level + 1))
        if name == '':
            results.append('{}/'.format(folder_path.path.rstrip('/')))
        return sorted(results)
