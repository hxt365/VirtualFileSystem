from typing import List

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from filesystem import repositories as repo
from filesystem.exceptions import FileExisted, FileNotFound, InvalidFilename, MovedIntoSubFolder
from . import serializers
from .utils import get_input_fields
from ..models import FilePath


class CommandAPIView(GenericAPIView):
    """
    Generic API view that handles request containing command.
    """

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        All commands are sent within POST requests,
        because length of command arguments may exceed the limit of a GET request.
        Here we handle exceptions and return corresponding responses:
            - FileExisted
            - FileNotFound
            - InvalidFilename
            - MovedIntoSubFolder
        See filesystem/exceptions for more information.
        :return a HTTP response that contains result of the command or message of exception.
        """
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            try:
                return self.handle(**get_input_fields(serializer))
            except FileExisted:
                return Response(data='File existed.', status=status.HTTP_400_BAD_REQUEST)
            except FileNotFound:
                return Response(data='No such file or directory.', status=status.HTTP_400_BAD_REQUEST)
            except InvalidFilename:
                return Response(data='Invalid filename.', status=status.HTTP_400_BAD_REQUEST)
            except MovedIntoSubFolder:
                return Response(data='Cannot move to a subdirectory of itself.', status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                print(e)

    def handle(self, *args, **kwargs) -> Response:
        """
        Core logic of view.
        Need to handle the command here.
        :return a HTTP response that contains result of the command.
        """
        raise NotImplementedError


class CdAPIView(CommandAPIView):
    """
    API view that handles cd command. See README file for more information about the command.
    """
    serializer_class = serializers.CdSerializer

    def handle(self, folder_path: str, *args, **kwargs) -> Response:
        folder_path = FilePath(folder_path)
        folder = repo.get_file(filepath=folder_path)
        if not folder.is_folder:
            raise FileNotFound
        if folder_path.path != '/':
            folder_path.path += '/'
        res_data = {'folder_path': folder_path.path}  # Add trailing slash
        return Response(data=self.serializer_class(res_data).data,
                        status=status.HTTP_200_OK)


class CrAPIView(CommandAPIView):
    """
    API view that handles cr command. See README file for more information about the command.
    """
    serializer_class = serializers.CrSerializer

    def handle(self, path: str, p_flag: bool, data: str, *args, **kwargs) -> Response:
        filepath = FilePath(path)
        repo.create_file(filepath=filepath, p_flag=p_flag, data=data)
        return Response(status=status.HTTP_201_CREATED)


class CatAPIView(CommandAPIView):
    """
    API view that handles cat command. See README file for more information about the command.
    """
    serializer_class = serializers.CatSerializer

    def handle(self, file_path, *args, **kwargs) -> Response:
        filepath = FilePath(file_path)
        file = repo.get_file(filepath=filepath)
        # Cannot read data of folders
        if file.is_folder:
            raise FileNotFound
        return Response(data=self.serializer_class({'content': file.data}).data,
                        status=status.HTTP_200_OK)


class LsAPIView(CommandAPIView):
    """
    API view that handles ls command. See README file for more information about the command.
    """
    serializer_class = serializers.LsSerializer

    def handle(self, folder_path: str, *args, **kwargs) -> Response:
        folder_path = FilePath(folder_path)
        folder = repo.get_file(filepath=folder_path)
        if not folder.is_folder:
            raise FileNotFound
        # Results are sorted alphabetically
        results = [folder] + sorted(list(folder.get_children()), key=lambda f: f.name)
        # Add trailing slash for folders
        for item in results:
            if item.is_folder and item.name != '/':
                item.name += '/'

        return Response(data=self.serializer_class({'items': results}).data,
                        status=status.HTTP_200_OK)


class FindAPIView(CommandAPIView):
    """
    API view that handles find command. See README file for more information about the command.
    """
    serializer_class = serializers.FindSerializer

    def handle(self, folder_path: str, name: str, *args, **kwargs) -> Response:
        folder_path = FilePath(folder_path)
        results = repo.find(name=name, folder_path=folder_path)
        return Response(data=self.serializer_class({'results': results}).data,
                        status=status.HTTP_200_OK)


class UpAPIView(CommandAPIView):
    """
    API view that handles up command. See README file for more information about the command.
    """
    serializer_class = serializers.UpSerializer

    def handle(self, path: str, name: str, data: str, *args, **kwargs) -> Response:
        filepath = FilePath(path)
        repo.update_file(filepath=filepath, new_name=name, new_data=data)
        return Response(status=status.HTTP_200_OK)


class MvAPIView(CommandAPIView):
    """
    API view that handles mv command. See README file for more information about the command.
    """
    serializer_class = serializers.MvSerializer

    def handle(self, folder_path: str, path: str, *args, **kwargs) -> Response:
        filepath = FilePath(path)
        folder_path = FilePath(folder_path)
        repo.move_file(filepath=filepath, folder_path=folder_path)
        return Response(status=status.HTTP_200_OK)


class RmAPIView(CommandAPIView):
    """
    API view that handles rm command. See README file for more information about the command.
    """
    serializer_class = serializers.RmSerializer

    def handle(self, paths: List[str], **kwargs) -> Response:
        filepaths = [FilePath(path) for path in paths]
        repo.remove_file(filepaths=filepaths)
        return Response(status=status.HTTP_200_OK)
