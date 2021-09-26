from gettext import gettext as _

STATUS_CREATED = 0
STATUS_WORKING = 10
STATUS_DONE = 20
STATUS_ERROR = 30

STATUS_OPTIONS = [
    (STATUS_CREATED, _('Created')),
    (STATUS_WORKING, _('Working')),
    (STATUS_DONE, _('Done')),
    (STATUS_ERROR, _('Error'))
]
