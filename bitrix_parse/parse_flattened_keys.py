import re

__all__ = [
    'parse_flattened_keys',
]

from typing import Mapping, Text, Any


def _transform(data: Any) -> Any:
    """
    Рекурсивно изменить данные в словаре.
    """
    if not isinstance(data, dict):
        return data

    transformed_data = {key: _transform(value) for key, value in data.items()}

    # Словари вида "array": {"0": 123, "1": 456} превращаются в массив "array": [123, 456]
    if transformed_data and all(key.isdigit() for key in transformed_data):
        sorted_keys = sorted(transformed_data, key=int)
        indices = [int(key) for key in sorted_keys]
        if indices == list(range(len(indices))):
            return [transformed_data[key] for key in sorted_keys]

    return transformed_data


def parse_flattened_keys(data: Mapping[Text, Any]) -> dict:
    """
    Преобразовать плоские ключи form-data во вложенный словарь.
    Одинаковые ключи с [] на конце - собираются в список, даже если только один элемент.
    Ключи с последовательным индексами, начиная от [0] - собираются в сортированный список.
    Остальные ключи - сохраняют последнее значение.

    :param data: например, dict(request.POST.lists()).
    """
    result_data = {}

    for raw_key, raw_value in data.items():
        parts = re.findall(r'[^\[\]]+', raw_key)
        if not parts:
            continue

        if raw_key.endswith('[]'):
            value = raw_value if isinstance(raw_value, list) else [raw_value]
        elif isinstance(raw_value, list):
            value = raw_value[-1] if raw_value else raw_value
        else:
            value = raw_value

        current_level = result_data

        for part in parts[:-1]:
            current_level = current_level.setdefault(part, {})

        current_level[parts[-1]] = value

    return _transform(result_data)
