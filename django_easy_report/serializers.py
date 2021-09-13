from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder


class DjangoEasyReportJSONEncoder(DjangoJSONEncoder):

    def default(self, o):
        if isinstance(o, ValidationError):
            return o.message
        return super().default(o)
