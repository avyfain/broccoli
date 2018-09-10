import os
import json
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

SUBJECT = "Hi, maybe you can play one of these?"
MAX_PID = r.get('last') or -1
BASE_URL = 'http://sfbay.craigslist.org'

# for apartments this was "/search/apa/"
PATH = '/search/sfc/sss'
URL = BASE_URL + PATH

# Remove weird characters
USE_CHARS = string.ascii_letters + ''.join(str(i) for i in range(10)) + ' -$'

EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
TO = os.environ.get('TO').split(', ')

smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
smtp_server.ehlo()
smtp_server.login(EMAIL_USER, EMAIL_PASSWORD)


def scrape_craigslist(params):
    cur_max_pid = MAX_PID
    resp = requests.get(URL + PATH, params=params)
    soup = BeautifulSoup(resp.text, 'html.parser')
    items = soup.find_all(class_="result-row")

    for item in items:
        title = item.find('a', class_='hdrlnk')
        name = ''.join(i for i in title.text if i in USE_CHARS)
        path = title.attrs['href']
        pid = item.get('data-pid')
        if pid > MAX_PID \
           and item.get('data-repost-of') is None \
           and not 'squi' in name.lower() \
           and not 'epiphone' in name.lower():
            cur_max_pid = max(cur_max_pid, pid)
            yield name, path
    try:
        r.set('last', cur_max_pid)
    except Exception:
        pass


def assemble_email(items_info):
    items = "\n".join("<li><a href={}>{}</a></li>".format(path, name) for name, path in items_info)
    html = "<html><body><ul>{}</ul></html></body>".format(items)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = SUBJECT
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(TO)

    # Record the MIME types of both parts - text/plain and text/html.
    part = MIMEText(html, 'html')
    msg.attach(part)
    return msg.as_string()


def main():
    amps = list(scrape_craigslist({"query": 'vox+ac', "max_price": 500}))
    teles = list(scrape_craigslist({"query": 'fender+telecaster', "max_price": 800}))
    sg = list(scrape_craigslist({"query": 'gibson+sg', "max_price": 800}))
    stuff = amps + [('', '</br></br>')] + teles + [('', '</br></br>')] + sg
    if stuff:
        email_text = assemble_email(stuff)
        smtp_server.sendmail(EMAIL_USER, TO, email_text)
        smtp_server.close()


if __name__ == '__main__':
    main()
