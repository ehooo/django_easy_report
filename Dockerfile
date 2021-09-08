ARG PY_VERSION=3.7
FROM python:${PY_VERSION}-alpine
ARG DJANGO_VERSION=3.1.1

ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN apk update && apk add bash

ADD requirements.txt .
RUN echo "pip install django==${DJANGO_VERSION}" && \
    pip install -r requirements.txt
ADD ./test_web/requirements.txt ./test_web/requirements.txt
RUN pip install -r ./test_web/requirements.txt

ADD ./entrypoint.sh .
ADD README.md /code/
ADD *.py /code/
ADD ./django_easy_report/ /code/django_easy_report/
ADD ./test_web/ /code/test_web/
RUN python setup.py install && chmod 755 entrypoint.sh

CMD "/code/entrypoint.sh"
