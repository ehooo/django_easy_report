from celery import shared_task


@shared_task
def generate_report(report_pk):
    return


@shared_task
def notify_report_done(query_pk):
    return

