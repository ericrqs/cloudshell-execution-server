import os
import platform

import re
import signal
import subprocess

import sys


def string23(b):
    if sys.version_info.major == 3:
        if isinstance(b, bytes):
            return b.decode('utf-8', 'replace')
    return b or ''


class ProcessRunner():
    def __init__(self, logger):
        self._logger = logger
        self._current_processes = {}
        self._stopping_processes = []
        self._running_on_windows = platform.system() == 'Windows'

    def execute_throwing(self, command_list, identifier, env=None, directory=None):
        o, c = self.execute(command_list, identifier, env=env, directory=directory)
        if c:
            s = 'Error: %d: %s failed: %s' % (c, command_list, o)
            if self._logger:
                self._logger.error(s)
            raise Exception(s)
        return o, c

    def execute(self, command_list, identifier, env=None, directory=None):
        env = env or {}
        if True:
            pcommands = []
            for command in command_list:
                pcommand = command
                pcommand = re.sub(r':[^@:]*@', ':(password hidden)@', pcommand)
                pcommand = re.sub(r"CLOUDSHELL_PASSWORD:[^']*", 'CLOUDSHELL_PASSWORD:(password hidden)', pcommand)
                pcommands.append(pcommand)
            penv = dict(env)
            if 'CLOUDSHELL_PASSWORD' in penv:
                penv['CLOUDSHELL_PASSWORD'] = '(hidden)'

            if self._logger:
                self._logger.debug('Execution %s: Running %s with env %s' % (identifier, pcommands, penv))
        if self._running_on_windows:
            process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, env=env, cwd=directory)
        else:
            process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, preexec_fn=os.setsid, env=env, cwd=directory)
        self._current_processes[identifier] = process
        output = ''
        for line in iter(process.stdout.readline, b''):
            line = string23(line)
            if self._logger:
                self._logger.debug('Output line: %s' % line)
            output += line
        process.communicate()
        self._current_processes.pop(identifier, None)
        if identifier in self._stopping_processes:
            self._stopping_processes.remove(identifier)
            return None, -6000
        return output, process.returncode

    def stop(self, identifier):
        if self._logger:
            self._logger.info('Received stop command for %s' % identifier)
        process = self._current_processes.get(identifier)
        if process is not None:
            self._stopping_processes.append(identifier)
            if self._running_on_windows:
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGTERM)

