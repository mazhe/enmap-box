"""
This scripts generates some reports stats related to the EnMAP-Box repository
"""
import argparse
import csv
from typing import List, Dict

import requests
import datetime
import inspect
import json
import os
import pathlib
import re
import unittest
import urllib.request
import xml.etree.ElementTree as etree
import pandas as pd

from xlsxwriter.workbook import Workbook

from enmapbox import DIR_REPO_TMP
from enmapbox import initAll
from enmapbox.algorithmprovider import EnMAPBoxProcessingProvider
from enmapbox.gui.applications import ApplicationWrapper, EnMAPBoxApplication
from enmapbox.gui.enmapboxgui import EnMAPBox
from enmapbox.testing import start_app
from qgis.PyQt.QtWidgets import QMenu
from qgis.core import QgsProcessing, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination, \
    QgsProcessingOutputVectorLayer, QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource, \
    QgsProcessingOutputRasterLayer, QgsProcessingParameterVectorLayer, QgsProcessingParameterVectorDestination, \
    QgsProcessingParameterMapLayer, QgsProcessingParameterMultipleLayers, QgsProcessingParameterFile, \
    QgsProcessingOutputFile, QgsProcessingParameterFolderDestination, QgsProcessingOutputFolder, \
    QgsProcessingParameterFileDestination, QgsProcessingOutputHtml, QgsProcessingParameterEnum, \
    QgsProcessingParameterBoolean, QgsProcessingAlgorithm


def linesOfCode(path) -> int:
    path = pathlib.Path(path)
    lines = 0
    if path.is_dir():
        for e in os.scandir(path):
            if e.is_dir():
                lines += linesOfCode(e.path)
            elif e.is_file and e.name.endswith('.py'):
                with open(e.path, 'r', encoding='utf-8') as f:
                    lines += len(f.readlines())
    return lines


def report_downloads() -> pd.DataFrame:
    url = r'https://plugins.qgis.org/plugins/enmapboxplugin'

    hdr = {'User-agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=hdr)
    response = urllib.request.urlopen(req)

    html = response.read().decode('utf-8')

    html = re.search(r'<table .*</table>', re.sub('\n', ' ', html)).group()
    html = re.sub(r'&nbsp;', '', html)
    html = re.sub(r'xmlns=".*"', '', html)
    html = re.sub(r'>&times;<', '><', html)
    tree = etree.fromstring(html)
    table = tree
    #  table = tree.find('.//table[@class="table table-striped plugins"]')
    DATA = {k: [] for k in ['version', 'minQGIS', 'experimental', 'downloads', 'uploader', 'datetime']}
    for tr in table.findall('.//tbody/tr'):
        tds = list(tr.findall('td'))
        """
        <td><a title="Version details" href="/plugins/enmapboxplugin/version/3.11.0/">3.11.0</a></td>
        <td>no</td>
        <td>3.24.0</td>
        <td>1668</td>
        <td><a href="/plugins/user/janzandr/admin">janzandr</a></td>
        <td><span class="user-timezone">2022-10-09T22:36:01.698509+00:00</span></td>
        """
        s = ""
        versionEMB = tds[0].find('.//a').text
        versionQGIS = tds[2].text
        experimental = tds[1].text.lower() == 'yes'
        downloads = int(tds[3].text)
        uploader = tds[4].find('a').text
        datetime = tds[5].find('span').text
        DATA['version'].append(versionEMB)
        DATA['minQGIS'].append(versionQGIS)
        DATA['experimental'].append(experimental)
        DATA['downloads'].append(downloads)
        DATA['datetime'].append(datetime)
        DATA['uploader'].append(uploader)

    df = pd.DataFrame.from_dict(DATA)

    df = df.query('experimental == False')
    df.sort_values(by=['datetime'], inplace=True, ascending=False)
    return df


def toDate(text, format: str = '%Y-%m-%dT%H:%M:%SZ') -> datetime.datetime:
    return datetime.datetime.strptime(text, format)


def report_github_issues_QGIS(authors=['jakimowb', 'janzandr']) -> pd.DataFrame:
    """

    is:issue created:2022-07-01..2022-12-31
    is:issue closed:2022-07-01..2022-12-31
    """

    # GitHub repository owner and name
    owner = 'qgis'
    repo = 'QGIS'

    # Define the date range
    start_date = toDate('2023-01-01', '%Y-%m-%d')
    end_date = toDate('2023-06-30', '%Y-%m-%d')

    today = datetime.datetime.now().isoformat().split('T')[0]

    PATH_GH_JSON = pathlib.Path(__file__).parents[1] / 'tmp' / f'githubissues.{today}.QGIS.json'

    if not PATH_GH_JSON.is_file():
        os.makedirs(PATH_GH_JSON.parent, exist_ok=True)
        # Your GitHub personal access token
        assert 'GITHUB_TOKEN' in os.environ, 'GITHUB_TOKEN is not set. ' \
                                             'Read https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens for details.'
        token = os.environ['GITHUB_TOKEN']

        # Create a session and set the authorization header
        session = requests.Session()
        session.headers.update({'Authorization': f'token {token}'})

        # Get the list of issues from the GitHub API
        issues_url = f'https://api.github.com/repos/{owner}/{repo}/issues'
        params = {
            'state': 'all',  # 'all' includes open and closed issues
            'per_page': 100,  # Adjust as needed
            'creator': ','.join(authors),
        }
        all_issues = []

        n_pages = 1
        while True:
            print(f'Read page {n_pages}...')
            response = session.get(issues_url, params=params)

            response.raise_for_status()
            all_issues.extend(response.json())

            # Check if there are more pages of issues
            link_header = response.headers.get('Link', '')
            if 'rel="next"' not in link_header:
                break

            rx = re.compile(r'<(.[^>]+)>; *rel="next"')

            # Extract the URL for the next page
            link = [l.strip() for l in link_header.split(',') if 'rel="next"' in l]
            if len(link) > 0:
                link = link[0]
                issues_url = rx.match(link).group(1)
            else:
                response.close()
                break
            n_pages += 1
        with open(PATH_GH_JSON, 'w') as f:
            json.dump(all_issues, f)

    with open(PATH_GH_JSON, 'r') as f:
        all_issues = json.load(f)

    # filter by authors

    pull_requests = [i for i in all_issues if 'pull_request' in i]
    issues = [i for i in all_issues if 'pull_request' not in i]
    if True:
        for i in issues:
            if i['closed_at'] and toDate(i['closed_at']) > end_date:
                i['closed_at'] = None
            else:
                s = ""

    # Filter issues within the date range

    created_in_report_period = [i for i in issues if start_date <= toDate(i['created_at']) <= end_date]
    created_before_but_touched = [i for i in issues if toDate(i['created_at']) < start_date
                                  and start_date <= toDate(i['updated_at']) <= end_date]

    def printInfos(issues: List[dict], labels=['duplicate', 'wontfix']):
        is_closed = []
        is_open = []

        issues_by_label: Dict[str, List[dict]] = dict()
        for i in issues:
            if i['closed_at'] is None:
                is_open.append(i)
            else:
                is_closed.append(i)

            for label in i['labels']:
                n = label['name']
                issues_by_label[n] = issues_by_label.get(n, []) + [i]

        n_t = len(issues)
        print(' Total: {:3}'.format(n_t))
        if n_t > 0:
            n_o = len(is_open)
            n_c = len(is_closed)

            print('  Open: {:3} {:0.2f}%'.format(n_o, n_o / n_t * 100))
            print('Closed: {:3} {:0.2f}%'.format(n_c, n_c / n_t * 100))
            for label in labels:
                print(f' {label}: {len(issues_by_label.get(label, []))}')

    print(f'By today: {today}')
    print(f'Issues created in reporting period: {start_date} to {end_date}:')
    printInfos(created_in_report_period)

    print(f'Issues created before {start_date} but handled in reporting period:')
    printInfos(created_before_but_touched)

    print('Total:')
    printInfos(created_before_but_touched + created_in_report_period)
    return None


def report_github_issues_EnMAPBox() -> pd.DataFrame:
    """

    is:issue created:2022-07-01..2022-12-31
    is:issue closed:2022-07-01..2022-12-31
    """

    # GitHub repository owner and name
    owner = 'EnMAP-Box'
    repo = 'enmap-box'

    # Define the date range
    start_date = toDate('2023-01-01', '%Y-%m-%d')
    end_date = toDate('2023-06-30', '%Y-%m-%d')

    today = datetime.datetime.now().isoformat().split('T')[0]

    PATH_GH_JSON = pathlib.Path(__file__).parents[1] / 'tmp' / f'githubissues.{today}.json'

    if not PATH_GH_JSON.is_file():
        os.makedirs(PATH_GH_JSON.parent, exist_ok=True)
        # Your GitHub personal access token
        assert 'GITHUB_TOKEN' in os.environ, 'GITHUB_TOKEN is not set. ' \
                                             'Read https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens for details.'
        token = os.environ['GITHUB_TOKEN']

        # Create a session and set the authorization header
        session = requests.Session()
        session.headers.update({'Authorization': f'token {token}'})

        # Get the list of issues from the GitHub API
        issues_url = f'https://api.github.com/repos/{owner}/{repo}/issues'
        params = {
            'state': 'all',  # 'all' includes open and closed issues
            'per_page': 100,  # Adjust as needed
        }
        all_issues = []

        while True:
            response = session.get(issues_url, params=params)

            response.raise_for_status()
            all_issues.extend(response.json())

            # Check if there are more pages of issues
            link_header = response.headers.get('Link', '')
            if 'rel="next"' not in link_header:
                break

            rx = re.compile(r'<(.[^>]+)>; *rel="next"')

            # Extract the URL for the next page
            link = [l.strip() for l in link_header.split(',') if 'rel="next"' in l]
            if len(link) > 0:
                link = link[0]
                issues_url = rx.match(link).group(1)
            else:
                response.close()
                break
        with open(PATH_GH_JSON, 'w') as f:
            json.dump(all_issues, f)

    with open(PATH_GH_JSON, 'r') as f:
        all_issues = json.load(f)
    pull_requests = [i for i in all_issues if 'pull_request' in i]
    issues = [i for i in all_issues if 'pull_request' not in i]
    if True:
        for i in issues:
            if i['closed_at'] and toDate(i['closed_at']) > end_date:
                i['closed_at'] = None
            else:
                s = ""

    # Filter issues within the date range

    created_in_report_period = [i for i in issues if start_date <= toDate(i['created_at']) <= end_date]
    created_before_but_touched = [i for i in issues if toDate(i['created_at']) < start_date
                                  and start_date <= toDate(i['updated_at']) <= end_date]

    def printInfos(issues: List[dict], labels=['duplicate', 'wontfix']):
        is_closed = []
        is_open = []

        issues_by_label: Dict[str, List[dict]] = dict()
        for i in issues:
            if i['closed_at'] is None:
                is_open.append(i)
            else:
                is_closed.append(i)

            for label in i['labels']:
                n = label['name']
                issues_by_label[n] = issues_by_label.get(n, []) + [i]

        n_t = len(issues)
        n_o = len(is_open)
        n_c = len(is_closed)
        print(' Total: {:3}'.format(n_t))
        print('  Open: {:3} {:0.2f}%'.format(n_o, n_o / n_t * 100))
        print('Closed: {:3} {:0.2f}%'.format(n_c, n_c / n_t * 100))
        for label in labels:
            print(f' {label}: {len(issues_by_label.get(label, []))}')

    print(f'By today: {today}')
    print(f'Issues created in reporting period: {start_date} to {end_date}:')
    printInfos(created_in_report_period)

    print(f'Issues created before {start_date} but handled in reporting period:')
    printInfos(created_before_but_touched)

    print('Total:')
    printInfos(created_before_but_touched + created_in_report_period)
    return None


def report_EnMAPBoxApplications() -> pd.DataFrame:
    app = start_app()
    initAll()
    emb = EnMAPBox()

    DATA = {'name': [],
            'version': [],
            # 'title':[],
            'locode': [],
            'license': [],
            }

    for a in emb.applicationRegistry.applicationWrapper():
        parentMenu = QMenu()
        a: ApplicationWrapper
        app: EnMAPBoxApplication = a.app

        path = pathlib.Path(inspect.getfile(app.__class__))
        app_dir = path.parent
        # loc1 = inspect.getsourcelines(app.__class__)
        loc = linesOfCode(app_dir)
        DATA['locode'].append(loc)
        DATA['name'].append(app.name)
        DATA['version'].append(app.version)
        DATA['license'].append(app.licence)
        # DATA['title'].append(a..title())

        menu = app.menu(parentMenu)
        s = ""
    df = pd.DataFrame.from_dict(DATA)
    df.sort_values(by=['name'], inplace=True)
    return df


def report_processingalgorithms() -> pd.DataFrame:
    emb = EnMAPBox.instance()
    if not isinstance(emb, EnMAPBox):
        emb = EnMAPBox()
    provider: EnMAPBoxProcessingProvider = emb.processingProvider()

    DATA = {k: [] for k in ['group', 'name', 'in', 'out', 'id', 'description', 'help']}

    NOT_HANDLED = set()
    LUT_LAYERTYPE = {QgsProcessing.SourceType.TypeMapLayer: ['R', 'V'],
                     QgsProcessing.SourceType.TypeFile: ['F'],
                     QgsProcessing.SourceType.TypeRaster: ['R'],
                     }
    for t in [QgsProcessing.SourceType.TypeVector, QgsProcessing.SourceType.TypeVectorAnyGeometry,
              QgsProcessing.SourceType.TypeVectorPoint,
              QgsProcessing.SourceType.TypeVectorLine,
              QgsProcessing.SourceType.TypeVectorPolygon]:
        LUT_LAYERTYPE[t] = ['V']

    def dataString(parameters) -> str:
        data_sources = set()
        for p in parameters:
            if isinstance(p, (QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination,
                              QgsProcessingOutputRasterLayer)):
                data_sources.add('R')
            elif isinstance(p, (QgsProcessingParameterVectorLayer, QgsProcessingOutputVectorLayer,
                                QgsProcessingParameterVectorDestination,
                                QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink)):
                data_sources.add('V')
            elif isinstance(p, QgsProcessingParameterMapLayer):
                data_sources.add('V')
                data_sources.add('R')
            elif isinstance(p, QgsProcessingParameterMultipleLayers):
                t = p.layerType()
                if t in LUT_LAYERTYPE.keys():
                    data_sources.update(LUT_LAYERTYPE[t])

            elif isinstance(p, (QgsProcessingParameterFile, QgsProcessingParameterFileDestination,
                                QgsProcessingOutputFile,
                                QgsProcessingParameterFolderDestination, QgsProcessingOutputFolder)):
                data_sources.add('F')
            elif isinstance(p, (QgsProcessingOutputHtml,)):
                data_sources.add('H')
            elif isinstance(p, (QgsProcessingParameterEnum, QgsProcessingParameterBoolean)):
                pass
            else:
                NOT_HANDLED.add(p.__class__.__name__)
        return ''.join(sorted(data_sources))

    for a in provider.algorithms():
        a: QgsProcessingAlgorithm
        DATA['id'].append(a.id())
        DATA['name'].append(a.name())
        DATA['group'].append(a.group())
        DATA['description'].append(re.sub('\n', ' ', a.shortDescription()))
        DATA['help'].append(a.shortHelpString())
        DATA['in'].append(dataString(a.parameterDefinitions()))
        DATA['out'].append(dataString(a.outputDefinitions()))

    df = pd.DataFrame.from_records(DATA)
    column_order = ['group', 'name', 'in', 'out', 'description', 'id', 'help']
    df = df.reindex(columns=column_order)

    df.sort_values(by=['group', 'name'], inplace=True)

    return df


def report_bitbucket_issues(self):
    # 1. open bitbucket,
    # goto repository settings -> issues -> Import & export
    # 2. export issues, extract zip file and copy db-2.0.json to JSON_DIR (defaults to <repo>/tmp)
    # 3. set report period with start_date / end_date

    """
    Syntax github issue request:
    https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests

    author:jakimowb type:issue created:>=2022-07-01 created:<=2022-12-31

    """

    JSON_DIR = pathlib.Path(__file__).parents[1] / 'tmp'
    start_date = datetime.date(2022, 1, 1)
    end_date = datetime.date(2022, 6, 30)

    PATH_DB_JSON = JSON_DIR / 'db-2.0.json'
    PATH_CSV_REPORT = JSON_DIR / f'issue_report_{start_date}_{end_date}.csv'
    assert PATH_DB_JSON.is_file(), 'No db-2.0.json, no stats!'
    assert start_date < end_date

    def csv2xlsx(path_csv):
        path_csv = pathlib.Path(path_csv)
        path_xlsx = path_csv.parent / f'{os.path.splitext(path_csv.name)[0]}.xlsx'
        workbook = Workbook(path_xlsx)
        # float_format = workbook.add_format({'num_format': ''})
        worksheet = workbook.add_worksheet()
        rxIsInt = re.compile(r'^\d+$')
        rxIsFloat = re.compile(r'^\d+([.,]\d*)?$')
        with open(path_csv, 'rt', encoding='utf8') as f:
            reader = csv.reader(f)
            for r, row in enumerate(reader):
                for c, col in enumerate(row):
                    if rxIsInt.match(col):
                        col = int(col)
                    elif rxIsFloat.match(col):
                        col = float(col)
                    worksheet.write(r, c, col)
        workbook.close()

    with open(PATH_DB_JSON, 'r', encoding='utf-8') as f:
        DB = json.load(f)

    # DS = pd.read_json(PATH_DB_JSON.as_posix())
    ISSUES = DB['issues']

    CREATED_ISSUES = [i for i in ISSUES if start_date
                      <= datetime.datetime.fromisoformat(i['created_on']).date()
                      <= end_date]
    UPDATED_ISSUES = [i for i in ISSUES if start_date
                      <= datetime.datetime.fromisoformat(i['updated_on']).date()
                      <= end_date]

    def byKey(ISSUES: list, key: str) -> dict:
        R = dict()
        for issue in ISSUES:
            k = issue[key]
            L = R.get(k, [])
            L.append(issue)
            R[k] = L
        return R

    CREATED_BY_STATUS = byKey(CREATED_ISSUES, 'status')
    UPDATED_BY_STATUS = byKey(UPDATED_ISSUES, 'status')

    print(f'Created: {len(CREATED_ISSUES)}')
    for k in sorted(CREATED_BY_STATUS.keys()):
        print(f'\t{k}: {len(CREATED_BY_STATUS[k])}')

    print(f'Updated: {len(UPDATED_ISSUES)}')
    for k in sorted(UPDATED_BY_STATUS.keys()):
        print(f'\t{k}: {len(UPDATED_BY_STATUS[k])}')

    with open(PATH_CSV_REPORT, 'w', encoding='utf-8', newline='') as f:
        states = ['new', 'open', 'on hold', 'resolved', 'closed', 'duplicate', 'wontfix', 'invalid']
        fieldnames = ['action', 'total'] + states
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        total_created = total_updated = 0
        ROW1 = {'action': 'created'}
        ROW2 = {'action': 'updated'}

        for s in states:
            total_created += len(CREATED_BY_STATUS.get(s, []))
            total_updated += len(UPDATED_BY_STATUS.get(s, []))
            ROW1[s] = len(CREATED_BY_STATUS.get(s, []))
            ROW2[s] = len(UPDATED_BY_STATUS.get(s, []))
        ROW1['total'] = total_created
        ROW2['total'] = total_updated
        writer.writerow(ROW1)
        writer.writerow(ROW2)

    csv2xlsx(PATH_CSV_REPORT)


class TestCases(unittest.TestCase):

    def test_github_EnMAPBox(self):
        report_github_issues_EnMAPBox()

    def test_github_QGIS(self):
        report_github_issues_QGIS()

    def test_report_downloads(self):
        df = report_downloads()
        print(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Install testdata', formatter_class=argparse.RawTextHelpFormatter)
    path_xlsx = pathlib.Path(DIR_REPO_TMP) / 'enmapbox_report.xlsx'
    parser.add_argument('-f', '--filename',
                        required=False,
                        default=path_xlsx.as_posix(),
                        help=f'Filename of XLSX file to save the report. Defaults to {path_xlsx}',
                        action='store_true')

    args = parser.parse_args()
    path_xlsx = pathlib.Path(args.filename)

    app = start_app(cleanup=False)
    initAll()

    os.makedirs(path_xlsx.parent, exist_ok=True)
    with pd.ExcelWriter(path_xlsx.as_posix()) as writer:
        dfDownloads = report_downloads()
        dfDownloads.to_excel(writer, sheet_name='Downloads')

        dfApp = report_EnMAPBoxApplications()
        dfApp.to_excel(writer, sheet_name='Apps')

        dfPAs = report_processingalgorithms()
        dfPAs.to_excel(writer, sheet_name='PAs')
