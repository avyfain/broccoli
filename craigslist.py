import os
import smtplib
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import redis
import requests
from bs4 import BeautifulSoup

try:
    r = redis.from_url(os.environ.get("REDIS_URL"))
except Exception:
    r = {}

MAX_PID = r.get('last') or -1
BASE_URL = 'http://sfbay.craigslist.org'
PATH = '/search/apa'
URL = BASE_URL + PATH
PARAMS = {'min_bedrooms': ['1'],
          'hasPic': ['1'],
          'min_bathrooms': ['1'],
          'laundry': ['1', '2', '3'],
          'max_bedrooms': ['2'],
          'availabilityMode': ['0'],
          'postal': ['94110'],
          'max_price': ['3500']
          }

# Remove weird characters
USE_CHARS = string.ascii_letters + ''.join(str(i) for i in range(10)) + ' -$'

EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
TO = os.environ.get('TO').split(', ')

smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
smtp_server.ehlo()
smtp_server.login(EMAIL_USER, EMAIL_PASSWORD)


def scrape_craigslist():
    cur_max_pid = MAX_PID
    resp = requests.get(URL + PATH, params=PARAMS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    apts = soup.find_all(class_="result-row")

    for apt in apts:
        title = apt.find('a', class_='hdrlnk')
        name = ''.join(i for i in title.text if i in USE_CHARS)
        path = title.attrs['href']
        pid = apt.get('data-pid')
        if pid > MAX_PID:
            cur_max_pid = max(cur_max_pid, pid)
            yield name, path
    try:
        r.set('last', cur_max_pid)
    except Exception:
        pass


def assemble_email(apts_info):
    apts = "\n".join("<li><a href={}{}>{}</a></li>".format(BASE_URL, path, name) for name, path in apts_info)
    html = "<html><body><ul>{}</ul></html></body>".format(apts)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Hi, maybe we can live in one of these?"
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(TO)

    # Record the MIME types of both parts - text/plain and text/html.
    part = MIMEText(html, 'html')
    msg.attach(part)
    return msg.as_string()


def main():
    apts_info = list(scrape_craigslist())
    if apts_info:
        email_text = assemble_email(apts_info)
        smtp_server.sendmail(EMAIL_USER, TO, email_text)
        smtp_server.close()


if __name__ == '__main__':
    main()
