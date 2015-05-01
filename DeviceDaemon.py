__author__ = 'bst'

import daemon
import os
import grp
import signal
import lockfile
import time
import logging

from Watchdog import Controller


def main():

    home = os.path.expanduser("~") + "/.DeviceDaemon"

    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s',
                        filename=home + "/controller.log",
                        level=logging.DEBUG)

    logger = logging.getLogger()
    logfile = logger.handlers[0].stream

    logger.info("Device daemon started")

    controller = Controller.WatchdogController(home, logger)

    context = daemon.DaemonContext(working_directory=home,
                                   files_preserve=[logfile],
                                   stdout=logfile,
                                   stderr=logfile,
                                   #stdout=open(home+"/stdout.log","a"),
                                   #stderr=open(home+"/stderr.log","a"),
                                   detach_process=True)

    context.signal_map = {
        signal.SIGTERM: controller.exit,
        signal.SIGUSR1: controller.reload,
    }

    controller.init()

    with context:
        controller.run()



if __name__ == '__main__':
    main()