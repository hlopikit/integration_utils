import re

import requests


def get_session_data(url, login, password):
    session = requests.session()
    r1 = session.get(url=url, auth=(login, password))
    sessid = re.findall(r'sessid=(\w+)', r1.text)[0]
    return session, sessid