from sqlalchemy.inspection import inspect


def to_dict(obj, include: list[str] | None = None) -> dict:
    data = {}
    mapper = inspect(obj).mapper
    for column in mapper.column_attrs:
        key = column.key
        data[key] = getattr(obj, key)
    if include:
        for rel_name in include:
            value = getattr(obj, rel_name)
            if isinstance(value, list):
                data[rel_name] = [to_dict(item) for item in value]
            elif value is not None:
                data[rel_name] = to_dict(value)
            else:
                data[rel_name] = value
    return data
