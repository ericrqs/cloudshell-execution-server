import getpass
import json
import subprocess
import sys
import time
import os
import logging
import re
import traceback
import platform
from logging.handlers import RotatingFileHandler

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer, CustomExecutionServerCommandHandler, PassedCommandResult, \
    FailedCommandResult, ErrorCommandResult, StoppedCommandResult

from cloudshell.custom_execution_server.daemon import become_daemon_and_wait
from cloudshell.custom_execution_server.process_manager import ProcessRunner

if platform.system() == 'Windows':
    default_log_dir = '.'
else:
    default_log_dir = '/var/log'

def string23(b):
    if sys.version_info.major == 3:
        if isinstance(b, bytes):
            return b.decode('utf-8', 'replace')
    return b or ''


def input23(msg):
    if sys.version_info.major == 3:
        return input(msg)
    else:
        return raw_input(msg)

jsonexample = '''Example config.json:
{
  "cloudshell_server_address" : "192.168.2.108",
  "cloudshell_port": 8029,
  "cloudshell_snq_port": 9000,

  "cloudshell_username" : "admin",
  // or
  "cloudshell_username" : "<PROMPT>",

  "cloudshell_password" : "myadminpassword",
  // or
  "cloudshell_password" : "<PROMPT>",

  "cloudshell_domain" : "Global",

  "cloudshell_execution_server_name" : "PythonSample1",
  "cloudshell_execution_server_description" : "CES in Python",
  "cloudshell_execution_server_type" : "Python",
  "cloudshell_execution_server_capacity" : 5,

  "log_directory": "/var/log",
  "log_level": "INFO",
  // CRITICAL | ERROR | WARNING | INFO | DEBUG
  "log_filename": "<EXECUTION_SERVER_NAME>.log"

}

Note: Remove all // comments before using
'''
configfile = os.path.join(os.path.dirname(__file__), 'config.json')

if len(sys.argv) > 1:
    usage = '''CloudShell custom execution server automatic self-registration and launch
Usage: 
    python %s                                      # run with %s
    python %s --config <path to JSON config file>  # run with JSON config file from custom location
    python %s -c <path to JSON config file>        # run with JSON config file from custom location

%s
The server will run in the background. Send SIGTERM to shut it down.
''' % (sys.argv[0], configfile, sys.argv[0], sys.argv[0], jsonexample)
    for i in range(1, len(sys.argv)):
        if sys.argv[i] in ['--help', '-h', '-help', '/?', '/help', '-?']:
            print(usage)
            sys.exit(1)
        if sys.argv[i] in ['--config', '-c']:
            if i+1 < len(sys.argv):
                configfile = sys.argv[i+1]
            else:
                print(usage)
                sys.exit(1)

try:
    with open(configfile) as f:
        o = json.load(f)
except:
    print('''%s

Failed to load JSON config file "%s".

%s

    ''' % (traceback.format_exc(), configfile, jsonexample))
    sys.exit(1)

cloudshell_server_address = o.get('cloudshell_server_address')
server_name = o.get('cloudshell_execution_server_name')
server_type = o.get('cloudshell_execution_server_type')

errors = []
if not cloudshell_server_address:
    errors.append('cloudshell_server_address must be specified')
if not server_name:
    errors.append('server_name must be specified')
if not server_type:
    errors.append('server_type must be specified. The type must be registered in CloudShell portal under JOB SCHEDULING>Execution Server Types.')
if errors:
    raise Exception('Fix the following in config.json:\n' + '\n'.join(errors))

cloudshell_username = o.get('cloudshell_username', '<PROMPT>')
cloudshell_password = o.get('cloudshell_password', '<PROMPT>')

if '<PROMPT>' in cloudshell_username:
    cloudshell_username = cloudshell_username.replace('<PROMPT>', input23('CloudShell username: '))
if '<PROMPT>' in cloudshell_password:
    cloudshell_password = cloudshell_password.replace('<PROMPT>', getpass.getpass('CloudShell password: '))

for k in list(o.keys()):
    v = str(o[k])
    if '<EXECUTION_SERVER_NAME>' in v:
        o[k] = o[k].replace('<EXECUTION_SERVER_NAME>', server_name)


server_description = o.get('cloudshell_execution_server_description', '')
server_capacity = int(o.get('cloudshell_execution_server_capacity', 5))
cloudshell_snq_port = int(o.get('cloudshell_snq_port', 9000))
cloudshell_port = int(o.get('cloudshell_port', 8029))
cloudshell_domain = o.get('cloudshell_domain', 'Global')
log_directory = o.get('log_directory', default_log_dir)
log_level = o.get('log_level', 'INFO')
log_filename = o.get('log_filename', server_name + '.log')


class MyCustomExecutionServerCommandHandler(CustomExecutionServerCommandHandler):

    def __init__(self, logger):
        CustomExecutionServerCommandHandler.__init__(self)
        self._logger = logger
        self._process_runner = ProcessRunner(self._logger)

    def execute_command(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
        BADCHAR = r'[^-@%.,_a-zA-Z0-9 ]'
        test_path = re.sub(BADCHAR, '_', test_path)

        logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        try:
            now = time.strftime("%Y-%m-%d_%H.%M.%S")
            resinfo = json.loads(reservation_json) if reservation_json and reservation_json != 'None' else None

            tt = [test_path]
            if test_arguments and test_arguments != 'None':
                tt += test_arguments.split(' ')

            try:
                output, mainretcode = self._process_runner.execute(tt, execution_id, env={
                    'CLOUDSHELL_RESERVATION_ID': reservation_id or 'None',
                    'CLOUDSHELL_SERVER_ADDRESS': cloudshell_server_address or 'None',
                    'CLOUDSHELL_SERVER_PORT': str(cloudshell_port) or 'None',
                    'CLOUDSHELL_USERNAME': cloudshell_username or 'None',
                    'CLOUDSHELL_PASSWORD': cloudshell_password or 'None',
                    'CLOUDSHELL_DOMAIN': cloudshell_domain or 'None',
                    'CLOUDSHELL_RESERVATION_INFO': reservation_json or 'None',
                })
            except Exception as uue:
                mainretcode = -5000
                output = 'External process crashed: %s: %s' % (str(uue), traceback.format_exc())

            if mainretcode == -6000:
                return StoppedCommandResult()

            self._logger.debug('Result of %s: %d: %s' % (tt, mainretcode, string23(output)))
            logname = 'output.log'
            logdata = output

            if mainretcode == 0:
                return PassedCommandResult(logname, logdata, 'text/plain')
            else:
                return FailedCommandResult(logname, logdata, 'text/plain')
        except Exception as ue:
            self._logger.error(str(ue) + ': ' + traceback.format_exc())
            raise ue

    def stop_command(self, execution_id, logger):
        logger.info('stop %s\n' % execution_id)
        self._process_runner.stop(execution_id)

log_pathname = '%s/%s' % (log_directory, log_filename)
logger = logging.getLogger(server_name)
handler = RotatingFileHandler(log_pathname, maxBytes=100000, backupCount=100)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)
if log_level:
    logger.setLevel(logging.getLevelName(log_level.upper()))

print('\nLogging to %s\n' % log_pathname)

server = CustomExecutionServer(server_name=server_name,
                               server_description=server_description,
                               server_type=server_type,
                               server_capacity=server_capacity,

                               command_handler=MyCustomExecutionServerCommandHandler(logger),

                               logger=logger,

                               cloudshell_host=cloudshell_server_address,
                               cloudshell_port=cloudshell_snq_port,
                               cloudshell_username=cloudshell_username,
                               cloudshell_password=cloudshell_password,
                               cloudshell_domain=cloudshell_domain,

                               auto_register=True,
                               auto_start=False)


def daemon_start():
    server.start()
    s = '\n\n%s execution server %s started\nTo stop %s:\nkill %d\n\nIt is safe to close this terminal.\n' % (server_type, server_name, server_name, os.getpid())
    logger.info(s)
    print (s)


def daemon_stop():
    msgstopping = "Stopping execution server %s, please wait up to 2 minutes..." % server_name
    msgstopped = "Execution server %s finished shutting down" % server_name
    logger.info(msgstopping)
    print (msgstopping)
    try:
        subprocess.call(['wall', msgstopping])
    except:
        pass
    server.stop()
    logger.info(msgstopped)
    print (msgstopped)
    try:
        subprocess.call(['wall', msgstopped])
    except:
        pass

become_daemon_and_wait(daemon_start, daemon_stop)
