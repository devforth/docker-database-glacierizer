import logging.config
from slack_sdk.webhook import WebhookClient

logging.config.fileConfig('logging.ini')
logger = logging.getLogger('ddgscheduler')


def send_slack_message(environment, message, type='SUCCESS'):
    webhook_url = environment['SLACK_WEBHOOK']
    project_name = environment['PROJECT_NAME']

    color_map = {
        'SUCCESS': '#36a64f',
        'FAIL': '#ee2700',
        'OTHER': '#FFCC00'
    }
    fallback_color = '#808080'

    logger.info(message)

    if project_name and len(project_name) > 0:
        project_name += " "

    if not webhook_url:
        return
    try:
        client = WebhookClient(webhook_url)
        response = client.send(
            attachments=[
                {
                    "color": color_map.get(type, fallback_color),
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"{project_name}Glacierizer"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": message
                            }
                        }
                    ]
                }
            ]
        )
    except Exception as e:
        logger.exception(e)


def sizeof_fmt(num):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if abs(num) < 1024.0:
            return "%.1f%s" % (num, unit)
        num /= 1024.0
    return "%.1f%s" % (num, 'PiB')
