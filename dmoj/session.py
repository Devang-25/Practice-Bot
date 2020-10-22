import requests
import bs4 as bs
import hashlib
from dmoj.language import Language
from dmoj.result import Result
from dmoj.testcase import Testcase

class InvalidSessionException(Exception):
    
    def __init__(self, code):
        self.code = code

class VerificationException(Exception):
    
    def __init__(self, hash):
        self.hash = hash

class Session:
    BASE_URL = 'https://dmoj.ca'
    gradingStatuses = ['QU', 'P', 'G']

    def __init__(self, token, user):
        self.token = token
        req = requests.get(self.BASE_URL + '/edit/profile/', headers={'Authorization': 'Bearer %s' % token})
        if req.status_code == 400 or req.status_code == 401:
            raise InvalidSessionException(req.status_code)
        doc = req.text
        soup = bs.BeautifulSoup(doc, 'lxml')
        self.handle = soup.find('span', attrs={'id' : 'user-links'}).find('b').contents[0]
        noAuthReq = requests.get(self.BASE_URL + '/user/' + self.handle)
        if noAuthReq.status_code == 400 or noAuthReq.status_code == 401:
            raise InvalidSessionException(noAuthReq.status_code)
        self.hash = hashlib.sha256((str(user.id) + self.handle).encode('utf-8')).hexdigest()
        if self.hash not in noAuthReq.text:
            raise VerificationException(self.hash)

    def __str__(self):
        return self.handle

    def getAuthRequest(self, url):
        return requests.get(url, headers={'Authorization': 'Bearer %s' % self.token})

    def postAuthRequest(self, url, data):
        return requests.post(url, headers={'Authorization': 'Bearer %s' % self.token}, data=data)

    def submit(self, problem, lang, code):
        global BASE_URL
        submitUrl = self.BASE_URL + '/problem/' + problem + '/submit'
        submitRes = self.postAuthRequest(submitUrl, {'source': code, 'language': str(lang)})
        if submitRes.status_code == 401:
            raise InvalidSessionException(submitRes.status_code)
        path = submitRes.url.split('/')
        return int(path[len(path)-1])

    def getTestcaseStatus(self, id):
        req = self.getAuthRequest(self.BASE_URL + '/widgets/single_submission?id=' + str(id))
        if req.status_code == 401:
            raise InvalidSessionException(req.status_code)
        soup = bs.BeautifulSoup(req.text, 'lxml')
        status = soup.find_all('span', attrs={'class' : 'status'})[0].contents[0]
        time = soup.find_all('div',  attrs={'class' : 'time'})[-1].contents[0].strip()
        memory = soup.find_all('div',  attrs={'class' : 'memory'})[0].contents[0]
        done = status not in self.gradingStatuses

        if memory == '---':
            memory = None
        if time == '---':
            time = None

        problemName = soup.find_all('div',  attrs={'class' : 'name'})[0].find('a').contents[0]

        req = self.getAuthRequest(self.BASE_URL + '/widgets/submission_testcases?id=' + str(id))
        if req.status_code == 401:
            raise InvalidSessionException(req.status_code)
        soup = bs.BeautifulSoup(req.text, 'lxml')
        raw_result = soup.find('body').contents[0]

        cases = []

        try:
            caseTable = soup.find_all('table', attrs={'class': 'submissions-status-table'})[0]
        except IndexError:
            return Result(cases, raw_result, status, problemName, time, memory, done)

        for row in caseTable.find_all('tr'):
            testcase = Testcase()
            try:
                testcase.id = int(row.get('id'))
            except ValueError:
                continue
            children = row.find_all('td')
            testcase.descriptor = children[0].find('b').contents[0]
            testcase.status = children[1].find('span').contents[0]
            testcase.details = {
                'time': children[2].find('span').contents[0].replace(',', ''),
                'memory': children[3].contents[0].replace('\xa0', ' ').replace(']', ''),
                'points': children[4].contents[0]
            }
            cases.append(testcase)            

        return Result(cases, raw_result, status, problemName, time, memory, done)        
