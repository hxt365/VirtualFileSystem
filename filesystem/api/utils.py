from typing import Dict, Any

from rest_framework.serializers import Serializer


def get_input_fields(serializer: Serializer) -> Dict[str, Any]:
    """
    Retrieve all input field values from a serializer.
    :param serializer: a serializer instance
    :return: a dictionary that contains field values and their corresponding names. Ex: {folder_path: /abc/}
    """
    serializer_fields = serializer.fields
    not_read_only_field_names = [name for name, field in serializer_fields.items() if not field.read_only]
    results = {name: serializer._validated_data[name] for name in not_read_only_field_names}
    return results
