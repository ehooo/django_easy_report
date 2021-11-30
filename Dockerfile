ARG PY_VERSION=3.7
FROM python:${PY_VERSION}-alpine AS builder
ENV PYTHONUNBUFFERED=1

ADD README.md .
ADD ./django_easy_report ./django_easy_report
ADD ./setup.py .
RUN python setup.py sdist

# -------------

FROM python:${PY_VERSION}-alpine
ARG DJANGO_VERSION=3.1.1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN apk update && apk add bash gcc musl-dev python3-dev libffi-dev openssl-dev cargo util-linux

COPY --from=builder /dist/django-easy-report-*.tar.gz ./

ADD ./test_web/requirements.txt .
RUN pip install django==${DJANGO_VERSION} && \
    pip install django-easy-report* && \
    pip install -r requirements.txt && rm requirements.txt

ADD ./entrypoint.sh .
ADD ./manage.py .
ADD ./test_web ./test_web
ADD ./django_easy_report/tests ./test_web/tests
ADD ./django_easy_report/fixtures ./test_web/fixtures
RUN echo "import os; \
FIXTURE_DIRS = [os.path.join(BASE_DIR, 'test_web', 'fixtures')];\
" >> ./test_web/settings.py

RUN chmod 755 entrypoint.sh

CMD "/code/entrypoint.sh"
