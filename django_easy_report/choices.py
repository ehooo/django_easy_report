
MODE_ENVIRONMENT = 0b0001
MODE_DJANGO_SETTINGS = 0b0010
MODE_CRYPTOGRAPHY = 0b1000
MODE_CRYPTOGRAPHY_ENVIRONMENT = MODE_CRYPTOGRAPHY | MODE_ENVIRONMENT
MODE_CRYPTOGRAPHY_DJANGO = MODE_CRYPTOGRAPHY | MODE_DJANGO_SETTINGS
