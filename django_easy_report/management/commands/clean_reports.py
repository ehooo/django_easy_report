from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from django_easy_report.models import ReportQuery


class Command(BaseCommand):
    help = 'Clean old reports'

    def add_arguments(self, parser):
        parser.add_argument('--until', type=str,
                            help='Date in format DD-MM-YYYY')
        parser.add_argument('--weeks', type=int)
        parser.add_argument('--days', type=int)

    def handle(self, *args, **options):
        until = None
        if options['until']:
            try:
                until = datetime.strptime(options['until'], '%d-%m-%Y')
            except ValueError:
                raise CommandError('Invalid date {}'.format(options['until']))
        elif options['weeks']:
            until = datetime.today() - timedelta(weeks=options['weeks'])
        elif options['days']:
            until = datetime.today() - timedelta(days=options['days'])

        reports = ReportQuery.objects.filter(created_at__lt=until)
        self.stdout.write(self.style.NOTICE('{} reports will be remoted'.format(reports.count())))
        for query in reports.iterator():
            query.delete()

        self.stdout.write(self.style.SUCCESS('Successfully removed'))
