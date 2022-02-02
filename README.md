# Django easy report
Django App for generate easily reports using [Celery](https://docs.celeryproject.org/en/stable/index.html)

Implments the following functions:
* Allows permissions by report.
* Allows multi storage systems.
* Allows prevalidation before generate.
* Detect same report params to allows cache it.
* Allows add requeters to a existing report.
* Allows customize send flow inside the report code.
* Allows secrets keys for storage setup based on:
[`django settings`](https://docs.djangoproject.com/en/3.2/topics/settings/),
[`environment`](https://docs.python.org/3/library/os.html#os.environ) or
[`cryptography`](https://pypi.org/project/cryptography/).
* Allows filter for storages and report classes.
* Action that allows generate report from Admin page.

# SetUp
* Install package from [pypi](https://pypi.org/project/django-easy-report/):
```shell
pip install django-easy-report
```
* Add application on `settings.py`:
```python
# ...
INSTALLED_APPS = [
# ...
    'django_easy_report',
# ...
]
```
* Add on `urls.py` the namespace `django_easy_report`:
```python
# ...
urlpatterns = [
    # ...
    path('reports/', include(('django_easy_report.urls', 'django_easy_report'), namespace='django_easy_report')),
    # ...
]
```
* Configure [celery](https://docs.celeryproject.org/en/stable/django/first-steps-with-django.html)

## Protect import dynamic classes
In order to block insecure classes on `ReportSender` and `ReportGenerator` models,
is allowed to define the on `settings.py` the setting `SENDER_CLASSES` and/or `REPORT_CLASSES`:
```python
# ...
SENDER_CLASSES = [
    'django.core.files.storage.FileSystemStorage',
]

REPORT_CLASSES = [
    'django_easy_report.reports.ReportModelGenerator',
    'django_easy_report.reports.AdminReportGenerator',
]
# ...
```
That values will be checked when model is saved and loaded,
that means that you will not able to use the reports
who have classes not listed on the proper setting.

# Howto
1. Create your code ([see example](./django_easy_report/tests/test_example.py)).
    1. Create `Form` class for validate input.
    2. Create Report class (extended from `ReportBaseGenerator`).
        1. Overwrite function `get_params` for know the users params and the report params.
        2. Overwrite function `validate` calling `super` to validate the form.
        3. Implement function `generate` function using `self.buffer` for write the report.
        4. Overwrite function `get_filename` to set report name.
        5. Overwrite function `get_message` to return the email body or raise `DoNotSend` to omit email send.
2. Create report `Sender` on Admin page.
3. Create `Report Generator` on Admin page.
4. Use you report endpoint defined on Admin page.

## Using Secrets
In order to protect your secrets you could use the `SecretKey` Model.
That allows you use 
[`django settings`](https://docs.djangoproject.com/en/3.2/topics/settings/),
[`environment`](https://docs.python.org/3/library/os.html#os.environ) or
[`cryptography`](https://pypi.org/project/cryptography/) to protect your secrets.

When you use that secrets you must create the model, on the Admin page.
The information that you enter must be on plain text.
The `key` field is only required when crypto is using.

Then you must create or edit a `ReportSender` model, adding on the key that you want to use.
The `replace word` will be used on the `Storage init params` field to replace with the value of the secret in plain text.
That allow you to replace the value of `Storage init params` from:
```json
{
  "my_secret": "Insecure secret"
}
```
to
```json
{
  "my_secret": $my_replace_word
}
```


## Using Admin Action
In order to allow generate reports based on admin page,
there is an action localed on `django_easy_report.actions.generate_report`.
You could see an example on: [test_web/custom/admin.py](./test_web/custom/admin.py)

To allows the generation flow on the standard flow you must
create `Report Generator` on Admin page using the class `django_easy_report.reports.AdminReportGenerator`.
In order to work you could only have one report using that class.

## API workflow
See doc as [OpenAPI format](./openapi.yml) or in [swagger](https://app.swaggerhub.com/apis-docs/ehooo/django_easy_report/1.0.0)

![work flow](https://raw.githubusercontent.com/ehooo/django_easy_report/main/doc/Django_easy_report-Generic%20flow.png)

### Examples
In both cases, the report is already generated by other user.

* Notify me when report is done

![notify me when report is done](https://raw.githubusercontent.com/ehooo/django_easy_report/main/doc/Django_easy_report-Notify%20example.png)
* Regenerate new report

![generate new report](https://raw.githubusercontent.com/ehooo/django_easy_report/main/doc/Django_easy_report-Regenerate%20report%20example.png)

## Test it with Docker
* Docker-compose
```shell
docker-compose up web -d
docker-compose exec web bash
```
* Docker
```shell
docker build . --tag="django_easy_report:latest"
docker run --publish=8000:8000 --name=django_easy_report_web django_easy_report:latest -d
docker exec -ti django_easy_report_web bash
```

* Run tests locally
```shell
docker build . --tag="django_easy_report:py38dj22" --build-arg PY_VERSION=3.8 --build-arg DJANGO_VERSION=2.2
docker run --rm --entrypoint /usr/local/bin/python --name=test_django_easy_report_web django_easy_report:py38dj22 manage.py test
```
Note that in that case you need rebuild with any change in the code


# MIT License
Copyright 2021 Victor Torre

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
