from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path
from typing import Callable, List, Dict, Union

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from filesystem import services as cache
from filesystem.exceptions import FileExisted, FileNotFound, InvalidFilename, ForbiddenOperation

FILEPATH_REGEX = r'^(\/[a-zA-Z0-9 _-]*)+(\/)*$'  # Any filepath must fully match this regular expression
FILENAME_REGEX = r'^[a-zA-Z0-9 _-]+$'  # Any filename must fully match this regular expression
MAX_PATH_LENGTH = 500  # maximum length of a filepath
MAX_NAME_LENGTH = 255  # maximum length of a filename
MAX_CONTENT_LENGTH = 1000  # maximum length of content of a file


class FilePath:
    """
    Each instance of this class represents an absolute path in the virtual file system.
    """

    def __init__(self, raw_path: str) -> None:
        self.path = self._clean(raw_path)

    @staticmethod
    def _clean(raw_path: str) -> str:
        """
        Normalize the raw file path by deleting aliases . (dot), .. (two dots):
        . (dot) means current directory.
        .. (two dots) means the parent directory of the current one.
        :param raw_path: a string of the raw file path.
        :return: a string of the normalized file path.
        :exception FileNotFound: raised if the normalized version of the raw file path is invalid.
        A file path is valid if:
        - It follow the pattern: /{name}/.../{name}
        - All names in the file path match regex /^[a-zA-Z0-9 _-]+$/
        Note: filepath '//' will be transformed to '/'.
        Note: The filepath /dirA/dirB/file.txt/.././ is considered valid and is normalized to /dirA/dirB. This allows
        long and complex filepaths to be preprocessed and hence processed quickly.
        """
        normalized_path = os.path.normpath(raw_path)
        if normalized_path == '//':
            normalized_path = '/'
        filepath_pattern = re.compile(FILEPATH_REGEX)
        if filepath_pattern.fullmatch(normalized_path) is None:
            raise FileNotFound
        return normalized_path

    def parent(self) -> FilePath:
        """
        Return the filepath of the parent directory of a given filepath
        Ex: /a/b/c  -> /a/b
            /a/b/c/ -> a/b
            //      -> //
            /       -> /
        :return: an FilePath instance contains the filepath of the parent directory
        """
        path = Path(self.path).parent
        return FilePath(path)

    def dirs(self) -> List[str]:
        """
        Extract filenames in the filepath.
        Ex: /a/b/c -> [a,b,c]
        :return: a list of filenames.
        """
        filenames = self.path.strip('/').split('/')
        if filenames == ['']:
            filenames = []
        return filenames


class AbstractFile(models.Model):
    """
    In file systems, files are entities that contain data.
    Each file has an globally unique id number (like inode number in Unix fs) and is created automatically by Django.
    """

    # Each file has a name, which has max length of 255 characters.
    # Name should be indexed to accelerate access speed, because we do a lot of look up based on it.
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    # The timestamp when the file is created, automatically set by Django
    created_at = models.DateTimeField(auto_now_add=True)
    # The timestamp when the file is updated, automatically set by Django when the file is updated
    # An update of child file will only propagate one level, that means the "grand-parent" folder will not be aware of
    # the update. This design decision makes the file system more robust, as there is no need to acquire read and write
    # locks during transactions for updating "higher-level" parent folder. Another reason is that users often do not
    # make use of updated_at information of a folder. So overall, this tradeoff is okay.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def only_folder(method: Callable):
    """
    This decorator the class method to be called only if the File instance is a folder.
    :param method: the class method that is about to be called.
    :return: a wrapper for the class method.
    :exception ForbiddenOperation: raised when normal files want to call the method.
    """

    def wrapper(self: File, *args, **kwargs):
        """
        :param self: a instance of File model
        """
        if self.is_folder:
            return method(self, *args, **kwargs)
        raise ForbiddenOperation

    return wrapper


class File(AbstractFile):
    """
    Similar to Unix file system, in this system, a folder (or directory), which is a group of files (neither normal
    files and sub-folders), is also a special type of file. Hence the word "file" will be used to refer to both normal
    files and folders.
    We say folder A is parent folder of file or sub-folder B and B is child of folder A if B is within A.
    The file system can be represented as a tree data structure.
    So the root directory has a path of "/" and name of '/' (which is unique), it always exists in the file system and
    has no parent.
    Names of files that reside in the same folder are different.
    """

    # If the parent folder is deleted, then all of its children will be deleted too.
    parent = models.ForeignKey('self', related_name="children", on_delete=models.CASCADE, null=True)
    # A file only contains text data, which can not be blank, but can be null when it is a folder
    data = models.TextField(null=True)
    # This field takes True value if the file is a folder. Otherwise, this field takes False value.
    is_folder = models.BooleanField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._size = None  # See size property method bellow

    def to_json(self):
        """
        Convert an object to json
        """

        def default(o):
            if isinstance(o, (datetime.date, datetime.datetime)):
                return o.isoformat().replace('+00:00', 'Z')

        return json.dumps({
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'parent_id': self.parent_id,
            'data': self.data,
            'is_folder': self.is_folder,
            '_size': self._size
        }, default=default)

    def clean(self):
        """
        We want to ensure that:
        - each file must have one parent, except the root directory.
        - content of a file is not blank and folders don't contain text data.
        - only folders can contains files.
        - filename fully matches the filename regex.
        :raise ValidationError when the conditions are violated.
        :raise InvalidFilename if the name is invalid.
        """
        if (self.is_folder and self.data is not None) or (not self.is_folder and self.data is None):
            raise ValidationError('a file contains wrong data')
        if self.parent_id is None:
            raise ValidationError('a file must have one parent')
        if not self.parent.is_folder:
            raise ValidationError('a file can not contain other files')

        pattern = re.compile(FILENAME_REGEX)
        if pattern.fullmatch(self.name) is None:
            raise InvalidFilename

    def save(self, *args, **kwargs):
        """
        This method is called when a file is about to be saved.
        Developers should avoid File.objects.create, because it force a file to be saved without validation. Should use
        save() method instead.
        :param args:
        :param kwargs:
        :return:
        """
        if 'force_insert' not in kwargs and 'force_update' not in kwargs:
            self.clean()
        super().save(*args, **kwargs)

    @only_folder
    def get_children(self) -> List[File]:
        """
        Only work for folders.
        Retrieve all children (neither folders and normal files) that are direct children of the folder.
        :return: a queryset of File instances.
        Note: Return an empty queryset if the folder has none children.
        """
        cache_children_ids = cache.get_children_ids(folder_id=self.id)
        if cache_children_ids:
            children = [self._get_child_by_id(id) for id in cache_children_ids]
            return children
        else:
            children = list(self.children.all())
            cache.set_children(self.id, children)
            return children

    @only_folder
    def _get_child_by_id(self, file_id: int) -> File:
        cache_data = cache.get_data(file_id=file_id)
        if cache_data:
            file = dict_to_file(cache_data)
            return file
        else:
            file = self.children.get(id=file_id)
            cache.set_data(file)
            return file

    @only_folder
    def get_child(self, filename: str) -> File:
        """
        Only work for folders.
        Retrieve one child (neither a folder and a normal file) that is direct child of the folder and match the name.
        :param filename: a string of the desired filename.
        :return: an instance of the desired file.
        :exception FileNotFound: raised when the file with desired name does not exist.
        """
        try:
            children = self.get_children()
            if children:
                # Search child by name
                child = next((child for child in children if child.name == filename), None)
                if child:
                    return child
                raise FileNotFound
            else:
                return self.children.get(name=filename)
        except File.DoesNotExist:
            raise FileNotFound

    @only_folder
    def add_child(self, file: File) -> None:
        """
        Only work for folders.
        Set parent of the file to the current folder.
        This method should be wrap in a transaction to ensure atomicity.
        :param file: an instance of Folder or File models, it can be either saved or not.
        :exception FileExisted: raised when the name of the child is duplicated in the folder.
        """
        try:
            self.get_child(file.name)
            raise FileExisted
        except FileNotFound:
            if file.parent_id:
                cache.rm_child(file.parent_id, file.id)  # when move files
            file.parent = self
            file.save()
            self.updated_at = timezone.now()
            self.save(force_update=True)
            cache.add_child(folder=self, file=file)

    @only_folder
    def remove_child(self, filename: str) -> None:
        """
        Only work for folders.
        Delete a direct child of the folder based on its name.
        This method should be wrap in a transaction to ensure atomicity. One reason is that cascading delete may fail
        in the middle of the process.
        :param filename: a string of the name of the child, which is about to be deleted.
        """
        # Should preserve this order for correct cache invalidation
        self.updated_at = timezone.now()
        child = self.get_child(filename)
        cache.rm_child(folder_id=self.id, file_id=child.id)
        child.delete()
        self.save(force_update=True)

    @property
    def size(self):
        """
        Get size of the file. We calculate the size every time to get the consistent value.
         Size of a folder is the total size of all files within the folder.
         Size of a normal file is the number of characters in its data.
        :return:
        """
        # check data in cache
        cache_data = cache.get_data(file_id=self.id)
        if cache_data and cache_data['_size'] is not None:
            self._size = cache_data['_size']
        else:
            if not self.is_folder:
                self._size = len(self.data)
            else:
                self._size = 0
                for child in self.get_children():
                    self._size += child.size

        cache.set_data(file=self)  # update size
        return self._size


def dict_to_file(dict: Dict) -> Union[File]:
    """
    Convert a dict to a file instance
    """
    size = None
    if '_size' in dict:
        size = dict.pop('_size')
    file = File(**dict)
    if size:
        file._size = size
    return file
