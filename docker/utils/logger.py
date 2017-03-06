# -*- coding: utf-8 -*-
#
# Dmitriy Miroshnichenko - 2017
# This module implements Logger.

import logging
import datetime

DEFAULT_DOCKER_LOG_LEVEL = 'DEBUG'

# initialize Main Parent Logger:
urllog = logging.getLogger('requests.packages.urllib3.connectionpool')
log = logging.getLogger("ProvisioningPython")

if not len(log.handlers):

    now = datetime.datetime.now()
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(filename)-25s[Line:%(lineno)d] %(levelname)-10s[%(asctime)s] %(message)s")
    handler.setFormatter(formatter)

    urllog.addHandler(handler)
    log.addHandler(handler)

    log.setLevel(level=DEFAULT_DOCKER_LOG_LEVEL)
    urllog.setLevel(level=DEFAULT_DOCKER_LOG_LEVEL)

    log.propagate = False
    urllog.propagate = False
