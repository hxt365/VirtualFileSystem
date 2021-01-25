class InvalidFilename(Exception):
    """
    Raised when the filename is invalid. A filename is invalid if it does not fully match regex /^[a-zA-Z0-9 _-]+$/
    """


class FileNotFound(Exception):
    """
    Raised when the desired file does not exist in the file system.
    """


class FileExisted(Exception):
    """
    Raised when system creates a file that are already existed or moves a file to a folder, in which has another file
    with the same name.
    """


class MovedIntoSubFolder(Exception):
    """
    Raised when a folder is moved into its sub-folder.
    """


class ForbiddenOperation(Exception):
    """
    Raised when normal files try to call methods, that only support folders
    """
