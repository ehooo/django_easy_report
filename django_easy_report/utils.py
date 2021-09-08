import json


def import_class(class_name):
    mod_name, cls_name = class_name.rsplit('.', 1)
    module = __import__(mod_name, fromlist=[cls_name])
    try:
        return getattr(module, cls_name)
    except AttributeError:
        raise ImportError('Cannot import class {}'.format(class_name))


def create_class(class_name, json_params):
    cls = import_class(class_name)
    kwargs = {}
    if json_params:
        kwargs = json.loads(json_params)
    return cls(**kwargs)
