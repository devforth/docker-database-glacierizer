import logging.config

from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler

from env import get_env
from server import AuthServer
from dump import dump_database
from slack import send_slack_message

logging.config.fileConfig('logging.ini')
logger = logging.getLogger('ddgscheduler')


if __name__ == "__main__":
    environment = get_env()

    if environment.get('TEST'):
        import time
        time.sleep(10)
        dump_database(environment)
        time.sleep(300)
    else:
        dumper_scheduler = BackgroundScheduler()
        dumper_scheduler.add_job(lambda: dump_database(environment), CronTrigger.from_crontab(environment.get('CRON')))
        dumper_scheduler.start()

        if environment.get('START_MANUAL_MANAGEMENT_SERVER'):
            def on_get():
                send_slack_message(environment, 'Backup triggered from server', 'OTHER')
                dump_database(environment)
                return f"{environment['PROJECT_NAME']} Backup Done"

            server = AuthServer(('', environment.get('MANUAL_MANAGEMENT_PORT')), logger)
            server.set_on_get(on_get)
            server.serve_forever()
