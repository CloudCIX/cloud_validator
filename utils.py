# stdlib
import os
# local
from settings import ROBOT_USERNAME, ROBOT_PASSWORD, ROBOT_API_KEY
# cloudcix
os.environ['CLOUDCIX_SETTINGS_MODULE'] = 'settings'
from cloudcix import api  # noqa: E402


def get_robot_token():
    """
    Generates an `admin` token using the credentials specified in the settings module
    (``CLOUDCIX_API_USERNAME``, ``CLOUDCIX_API_PASSWORD``, and ``CLOUDCIX_API_KEY``).
    """
    data = {
        'email': ROBOT_USERNAME,
        'password': ROBOT_PASSWORD,
        'api_key': ROBOT_API_KEY,
    }
    response = api.Membership.token.create(data=data)
    if response.status_code == 201:
        return response.json()['token']
    raise Exception(response.json()['error_code'])
