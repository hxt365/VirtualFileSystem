from typing import Union

from rest_framework import serializers

from filesystem.models import File, MAX_PATH_LENGTH, MAX_NAME_LENGTH, MAX_CONTENT_LENGTH


class CdSerializer(serializers.Serializer):
    """
    Serializer for cd (change directory) command.
    Input: a raw folder path.
    Output: a normalized folder path.
    """
    folder_path = serializers.CharField(max_length=MAX_PATH_LENGTH, required=True)


class CrSerializer(serializers.Serializer):
    """
    Serializer for cr (create) command.
    Input: a raw filepath, p flag (optional), new data (optional).
    """
    path = serializers.CharField(max_length=MAX_PATH_LENGTH, write_only=True)
    data = serializers.CharField(allow_null=True, write_only=True)
    p_flag = serializers.BooleanField(allow_null=True, write_only=True)

    def validate_p_flag(self, p_flag: Union[bool, None]) -> bool:
        """
        Set default p_flag = False.
        """
        if p_flag is None:
            return False
        return p_flag


class CatSerializer(serializers.Serializer):
    """
    Serializer for cat (show content) command.
    Input: a raw filepath.
    Output: content of the file at filepath.
    """
    file_path = serializers.CharField(max_length=MAX_PATH_LENGTH, write_only=True)
    content = serializers.CharField(max_length=MAX_CONTENT_LENGTH, read_only=True)


class FileSerializer(serializers.ModelSerializer):
    """
    Serialize meta-data of a file: name, created_at, updated_at, size.
    """

    class Meta:
        model = File
        fields = ['name', 'created_at', 'updated_at', 'size']


class LsSerializer(serializers.Serializer):
    """
    Serializer for ls (list items) command.
    Input: a raw folder path.
    Output: a list of meta-data information of direct children of the file (see FileSerializer).
    """
    folder_path = serializers.CharField(max_length=MAX_PATH_LENGTH, write_only=True)
    items = serializers.ListField(child=FileSerializer(), read_only=True)


class FilePathSerializer(serializers.Serializer):
    """
    Serializer for filepath.
    """
    filepath = serializers.CharField(max_length=MAX_PATH_LENGTH)


class FindSerializer(serializers.Serializer):
    """
    Serializer for find command.
    Input: a raw folder path and a name.
    Output: a list of filepaths.
    """
    name = serializers.CharField(max_length=MAX_NAME_LENGTH, allow_blank=True, write_only=True)
    folder_path = serializers.CharField(max_length=MAX_PATH_LENGTH, write_only=True)
    results = serializers.ListField(
        child=serializers.CharField(max_length=MAX_PATH_LENGTH),
        read_only=True)


class UpSerializer(serializers.Serializer):
    """
    Serializer for up (update) command.
    Input: a raw filepath, a new name, new data (optional).
    """
    path = serializers.CharField(max_length=MAX_PATH_LENGTH, write_only=True)
    name = serializers.CharField(max_length=MAX_NAME_LENGTH, write_only=True)
    data = serializers.CharField(max_length=MAX_CONTENT_LENGTH, allow_null=True, write_only=True)


class MvSerializer(serializers.Serializer):
    """
    Serializer for mv (move) command.
    Input: a raw filepath, a raw folder path.
    """
    path = serializers.CharField(max_length=MAX_PATH_LENGTH, write_only=True)
    folder_path = serializers.CharField(max_length=MAX_PATH_LENGTH, write_only=True)


class RmSerializer(serializers.Serializer):
    """
    Serializer for rm (remove) command.
    Input: a list of raw filepaths.
    """
    paths = serializers.ListField(
        child=serializers.CharField(max_length=MAX_PATH_LENGTH),
        write_only=True)
