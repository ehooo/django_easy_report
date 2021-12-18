from datetime import datetime, timedelta
import argparse

from django.core.management.base import BaseCommand

from django_easy_report.models import ReportQuery


def valid_date(str_date):
    try:
        return datetime.strptime(str_date, "%d-%m-%Y")
    except ValueError:
        msg = "Invalid date format, use DD-MM-YYYY.".format(str_date)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = 'Clean old reports'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--until',
                           type=valid_date,
                           help='Date in format DD-MM-YYYY')
        group.add_argument('--weeks', type=int)
        group.add_argument('--days', type=int)

    def handle(self, *args, **options):
        until = None
        if options['until'] is not None:
            until = options['until']
        elif options['weeks'] is not None:
            until = datetime.today() - timedelta(weeks=options['weeks'])
        elif options['days'] is not None:
            until = datetime.today() - timedelta(days=options['days'])

        reports = ReportQuery.objects.filter(created_at__lt=until)
        self.stdout.write(self.style.NOTICE('{} reports will be remoted'.format(reports.count())))
        for query in reports.iterator():
            query.delete()

        self.stdout.write(self.style.SUCCESS('Successfully removed'))
