import os
import signal
import time


def become_daemon_and_wait(on_start, on_exit, exit_signal=signal.SIGTERM):
    """
    Detaches from the terminal and sleeps in the main thread until the exit signal is received

    :param on_start: function with no arguments that starts the service threads
    :param on_exit: function with no arguments that stops the service threads (does not need to exit the process)
    :param exit_signal: signal that will trigger shutdown, by default SIGTERM
    :return:
    """
    def handler0(signum, frame):
        on_exit()
        os._exit(0)

    signal.signal(exit_signal, handler0)

    try:
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    except:
        pass

    if os.fork() == 0:
        os.setsid()
        if os.fork() == 0:
            os.chdir('/')
            os.umask(0)
        else:
            os._exit(0)
    else:
        os._exit(0)

    on_start()

    while True:
        time.sleep(60)
