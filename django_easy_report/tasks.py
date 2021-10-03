import logging

from celery import shared_task
from django.core.mail import EmailMessage
from django.db import transaction

from django_easy_report.constants import STATUS_ERROR, STATUS_DONE, STATUS_WORKING
from django_easy_report.exceptions import DoNotSend
from django_easy_report.models import ReportRequester, ReportQuery


logger = logging.getLogger(__name__)


@shared_task
def generate_report(query_pk):
    query = ReportQuery.objects.get(pk=query_pk)
    query.status = STATUS_WORKING
    query.save(update_fields=['status', 'updated_at'])
    try:
        report = query.get_report()
        query.filename = report.get_filename()
        query.mimetype = report.get_mimetype()
        report.generate()
        query.storage_path_location = report.save()
        query.status = STATUS_DONE
    except Exception:
        query.status = STATUS_ERROR
        raise
    finally:
        query.save(update_fields=['status', 'updated_at', 'mimetype', 'storage_path_location', 'filename'])
        notify_report_done.delay(
            list(ReportRequester.objects.filter(query_id=query_pk).values_list('id', flat=True))
        )


@shared_task
def notify_report_done(requester_pks):
    requesters = ReportRequester.objects.select_for_update().filter(pk__in=requester_pks, notified=False)
    with transaction.atomic():
        requester = requesters.last()
        if not requester:
            return
        if requesters.exclude(query=requester.query).exists():
            raise ValueError('All requesters must be from the same query ({})'.format(requester_pks))
        requester_pks = list(requesters.values_list('pk', flat=True))
        requesters.update(notified=True)

    query = requester.query
    report = query.get_report()
    sender = query.report.sender

    file_size = query.get_file_size()

    with_attachment = False
    link = query.get_url()

    if sender.email_from and file_size:
        if file_size < sender.size_to_attach:
            with_attachment = True

    content = None
    if with_attachment and file_size:
        with query.get_file(open_file=True) as attachment:
            content = attachment.read()
            attachment.close()

    requesters = ReportRequester.objects.filter(pk__in=requester_pks)
    for requester in requesters:
        try:
            email_to = report.get_email(requester)
            subject = report.get_subject(requester)
            body = report.get_message(requester.query.status, requester, with_attachment, link)

            mail = EmailMessage(
                subject,
                body,
                sender.email_from,
                [email_to],
            )
            if content:
                mail.attach(query.filename, content, query.mimetype)

            mail.send()
        except DoNotSend:
            logger.info('Report will not be send',
                        extra={'query_pk': query.pk, 'requester_pk': requester.pk})
            continue
        except Exception:
            # Only update notified if it was falling in other case the previous updated set as true
            requester.notified = False
            requester.save(update_fields=['notified'])
            logger.exception('Error sending report', extra={'query_pk': query.pk, 'requester_pk': requester.pk})
