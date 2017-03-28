import subprocess
import sys
import os
import logging
import platform
from logging.handlers import RotatingFileHandler

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer, CustomExecutionServerCommandHandler, PassedCommandResult

from cloudshell.custom_execution_server.daemon import become_daemon_and_wait

if platform.system() == 'Windows':
    default_log_dir = '.'
else:
    default_log_dir = '/var/log'


class MyCustomExecutionServerCommandHandler(CustomExecutionServerCommandHandler):

    def __init__(self):
        CustomExecutionServerCommandHandler.__init__(self)

    def execute_command(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
        logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        return PassedCommandResult('result.log', 'minimal execution server test output', 'text/plain')

    def stop_command(self, execution_id, logger):
        logger.info('stop %s\n' % execution_id)


log_pathname = '%s/%s' % ('.', 'minimal_execution_server.log')
logger = logging.getLogger('MinimalServer')
handler = RotatingFileHandler(log_pathname, maxBytes=100000, backupCount=100)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.getLevelName('DEBUG'))

print('\nLogging to %s\n' % log_pathname)


server_name = 'MinimalServer1'
server_type = 'Python'

server = CustomExecutionServer(server_name=server_name,
                               server_description='Minimal Execution Server',
                               server_type=server_type,
                               server_capacity=5,

                               command_handler=MyCustomExecutionServerCommandHandler(),

                               logger=logger,

                               cloudshell_host='localhost',
                               cloudshell_port=9000,
                               cloudshell_username='admin',
                               cloudshell_password='admin',
                               cloudshell_domain='Global',

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
