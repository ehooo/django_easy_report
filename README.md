# Django easy report
Django App for generate easily reports using [Celery](https://docs.celeryproject.org/en/stable/index.html)

## API workflow
See doc as [OpenAPI format](./openapi.yml)

![work flow](https://raw.githubusercontent.com/ehooo/django_easy_report/main/doc/Django_easy_report-Generic%20flow.png)

### Examples
* Notify me when report is done

![notify me when report is done](https://raw.githubusercontent.com/ehooo/django_easy_report/main/doc/Django_easy_report-Notify%20example.png)
* Regenerate new report

![generate new report](https://raw.githubusercontent.com/ehooo/django_easy_report/main/doc/Django_easy_report-Regenerate%20report%20example.png)

# SetUp
* Install package:
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

# Howto
1. Create your code ([see example](./django_easy_report/tests/test_example.py))
2. Create report Sender on Admin page
3. Create Report Generator on Admin page

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

# License
Copyright 2021 Victor Torre

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
