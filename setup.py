import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="django-easy-report",
    version="0.1.1",
    author="Victor Torre",
    author_email="web.ehooo@gmail.com",
    description="Django app for report generation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ehooo/django_easy_report",
    project_urls={
        "Bug Tracker": "https://github.com/ehooo/django_easy_report/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(include=('django_easy_report', 'django_easy_report.*')),
    python_requires=">=3.5",
    install_requires=[
        'django',
        'celery'
    ]
)
