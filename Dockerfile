ARG PY_VERSION=3.7
FROM python:${PY_VERSION}-alpine
ARG DJANGO_VERSION=3.1.1

ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN apk update && apk add bash

ADD requirements.txt .
RUN echo "pip install django==${DJANGO_VERSION}" && \
    pip install -r requirements.txt && rm requirements.txt
ADD ./test_web/requirements.txt .
RUN pip install -r requirements.txt && rm requirements.txt

ADD README.md .
ADD ./django_easy_report ./django_easy_report
ADD ./setup.py .
RUN python setup.py install && rm -fr django_easy_report setup.py README.md

ADD ./entrypoint.sh .
ADD ./manage.py .
ADD ./test_web ./test_web
RUN chmod 755 entrypoint.sh

CMD "/code/entrypoint.sh"
