# -*- coding: utf-8 -*-
#
# Author: Dmitriy Miroshnichenko, 2210605@gmail.com
# This module implements Logger.

import logging
import datetime

"""
# Level Reminder

CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
NOTSET = 0
"""


DEFAULT_DOCKER_LOG_LEVEL = 'DEBUG'

# Initialize Logger's:
urlliblog = logging.getLogger('requests.packages.urllib3.connectionpool')
log = logging.getLogger("ProvisioningPython")

# Helper function for defining logging level
def set_docker_log_level(level):
    log.setLevel(level=level)
    urlliblog.setLevel(level=level)

now = datetime.datetime.now() # set time
handler = logging.StreamHandler()
formatter = logging.Formatter("%(filename)-25s[Line:%(lineno)d] %(levelname)-10s[%(asctime)s] %(message)s")
handler.setFormatter(formatter)
urlliblog.addHandler(handler)
log.addHandler(handler)
log.propagate = False
urlliblog.propagate = False
