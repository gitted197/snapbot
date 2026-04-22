import urllib.request
from time import sleep


def get_snapcode(username):
    url = "https://app.snapchat.com/web/deeplink/snapcode?username={}&type=PNG"
    request_url = url.format(username)
    path = "snapcode.png"
    urllib.request.urlretrieve(request_url, path)
    sleep(0.5)