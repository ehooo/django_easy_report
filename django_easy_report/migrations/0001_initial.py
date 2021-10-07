from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportGenerator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.SlugField(max_length=32, unique=True)),
                ('class_name', models.CharField(help_text='Class name for for generate the report. It must be subclass of django_easy_report.reports.ReportBaseGenerator', max_length=64)),
                ('init_params', models.TextField(blank=True, help_text='JSON with init parameters', null=True)),
                ('permissions', models.CharField(blank=True, help_text='Comma separated permission list. Permission formatted as: &lt;content_type.app_label&gt;.&lt;permission.codename&gt;', max_length=1024, null=True)),
                ('always_generate', models.BooleanField(default=False, help_text='Do not search for similar reports previously generated')),
                ('always_download', models.BooleanField(default=False, help_text='Never will redirect to storage URL')),
                ('preserve_report', models.BooleanField(default=False, help_text='If model is deleted, do not remove the file on storage')),
            ],
        ),
        migrations.CreateModel(
            name='ReportQuery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('status', models.PositiveSmallIntegerField(choices=[(0, 'Created'), (10, 'Working'), (20, 'Done'), (30, 'Error')], default=0)),
                ('filename', models.CharField(max_length=32)),
                ('mimetype', models.CharField(default='application/octet-stream', max_length=32)),
                ('params', models.TextField(blank=True, null=True)),
                ('params_hash', models.CharField(max_length=128)),
                ('storage_path_location', models.CharField(blank=True, max_length=512, null=True)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='django_easy_report.reportgenerator')),
            ],
            options={
                'ordering': ('created_at',),
            },
        ),
        migrations.CreateModel(
            name='ReportSender',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(db_index=True, max_length=32, unique=True)),
                ('email_from', models.EmailField(blank=True, help_text='If have content email must be send when report is completed.', max_length=254, null=True)),
                ('size_to_attach', models.PositiveIntegerField(default=0, help_text='If size is bigger, the file will be upload using storage system, otherwise the file will be send as attached on the email.')),
                ('storage_class_name', models.CharField(help_text='Class name for for save the report. It must be subclass of django.core.files.storage.Storage', max_length=64)),
                ('storage_init_params', models.TextField(blank=True, help_text='JSON with init parameters', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ReportRequester',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_at', models.DateTimeField(auto_now_add=True)),
                ('user_params', models.TextField(blank=True, null=True)),
                ('notified', models.BooleanField(default=False)),
                ('query', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='django_easy_report.reportquery')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='reportgenerator',
            name='sender',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='django_easy_report.reportsender'),
        ),
    ]
