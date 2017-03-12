import pandas as pd
import numpy as np
import re
from lxml import etree
from lxml.html import tostring
from urllib import urlencode


class League(object):
    """ Represents league-wide data including settings and statistics.
        Parameters
        ----------
        leagueId: league id number str or int
        seasonId: season year str or int
        driver: if the league is password protected, you will need to pass a
        selenium webdriver in order to login to ESPN.
    """
    def __init__(self, leagueId, seasonId, login=None):
        self.leagueId = ('leagueId', str(leagueId))
        self.seasonId = ('seasonId', str(seasonId))
        self.leagueUrl = ('http://games.espn.com/flb/leagueoffice?' +
                          urlencode((self.leagueId, self.seasonId)))
        self.parser = etree.HTMLParser()
        self.login = login
        self.html = self._getHTML(self.leagueUrl, login=self.login)
        self.teamDict = self._getTeamDict()
        self.scoring = self._getScoring()
        # self.draft = self._getDraftType()

    def _getHTML(self, url, login=None):
        if login:
            login.get(url)
            html = login.lxml
        else:
            html = etree.parse(url, self.parser).getroot()
        return html

    def _getScoring(self):
        settingsUrl = ('http://games.espn.com/flb/leaguesetup/settings?' +
                       urlencode((self.leagueId, self.seasonId)))
        html = self._getHTML(settingsUrl, login=self.login)
        scoring = html.xpath('//td[@class="settingLabel"]/following-sibling'
                             '::td/text()')[0].strip()
        return scoring

    def _getTeamDict(self):
        """ Gets dict of team names and team Id numbers from league page.
        """
        teamIds = self.html.xpath('//ul[@id="games-tabs1"]/li/a/@href')
        teamIds = [re.findall('teamId=(\d+)', i)[0] for i in teamIds]
        teamNames = self.html.xpath('//ul[@id="games-tabs1"]/li/a/text()')
        teamNames = [name.strip().upper().replace('  ', ' ') for name in
                     teamNames]
        teamDict = dict(zip(teamIds, teamNames))
        return teamDict

    def _formatAuctionDraftTable(self, df):
        reStr = '(?P<PLAYER>.+?), (?P<TEAM>\w+)\xa0(?P<POS>\w+)'\
                '(?P<KEEPER>\xa0\xa0K$|$)'
        df = df.join(df[1].str.extract(reStr, expand=True))
        df.loc[df['KEEPER'] == u'\xa0\xa0K', 'KEEPER'] = True
        df.loc[np.logical_not(df['KEEPER']), 'KEEPER'] = False
        df.drop([0, 1, 2], axis=1, inplace=True)
        return df

    def _formatAuctionTable(self, df):
        """ Format html auction table string to pandas dataframe.
            Input: html table str
            Output: pandas dataframe
        """
        manager = df[0].ix[0]
        df['MANAGER'] = manager
        df.drop([0], inplace=True)
        df['PICK'] = pd.to_numeric(df[0])
        df['PRICE'] = pd.to_numeric(df[2].apply(lambda x: x[1:]))
        df = self._formatAuctionDraftTable(df)
        df = df[['MANAGER', 'PLAYER', 'PICK', 'TEAM', 'POS', 'PRICE',
                 'KEEPER']]
        return df

    def _formatDraftTable(self, html):
        """ Format html draft table string to pandas dataframe.
            Input: html table str
            Output: pandas dataframe
        """
        rnd = df[0].ix[0].replace('ROUND ', '')
        df.drop([0], inplace=True)
        df['ROUND'] = rnd
        df['PICK'] = pd.to_numeric(df[0])
        df['MANAGER'] = df[2]
        df = self._formatAuctionDraftTable(df)
        df = df[['ROUND', 'PICK', 'MANAGER', 'PLAYER', 'TEAM', 'POS',
                 'KEEPER']]
        return df

    def _formatDraft(self, df, draftType):
        if draftType == 'Auction Draft':
            return self._formatAuctionTable(df)
        elif (draftType == 'Snake Draft' or draftType == 'Offline Draft' or
              draftType == 'Autopick Draft'):
            return self._formatDraftTable(df)

    def _downloadDraftTable(self, teamId=None):
        """ Download leage "Draft Recap" page
            Input: teamId int
            Output: team or leaguewide draft results dataframe
        """
        if teamId:
            assert str(teamId) in self.teamDict
        draftUrl = ('http://games.espn.com/flb/tools/draftrecap?' +
                    urlencode((self.leagueId, self.seasonId)))
        html = self._getHTML(draftUrl, login=self.login)
        draftType = html.xpath('//b[text()="Type: "]/following-sibling::text()'
                               )[0].strip()
        draftXpath = '//div[@class="games-fullcol games-fullcol-extramargin'\
                     '"]/table/tr/td/table'
        draftTables = html.xpath(draftXpath)
        draftTable = pd.DataFrame()
        for table in draftTables:
            dfTable = pd.read_html(tostring(table))[0]
            df = self._formatDraft(dfTable, draftType)
            draftTable = pd.concat([draftTable, df])
        if teamId:
            return draftTable[draftTable['MANAGER'].str.upper() ==
                              self.teamDict[teamId]]
        else:
            return draftTable

    def _formatActiveStatsTable(self, df):
        """ Format active stats html table to data frame.
            Input: html table str, batter bool
            Output: pandas dataframe
        """
        df.drop(df.shape[0]-1, inplace=True)
        if df.iloc[:, 2].dtype == 'object':
            rows = df[df.iloc[:, 2] == '--'].index
            df.iloc[rows] = df.iloc[rows].replace(to_replace='--',
                                                  value=np.nan)
        df = df.apply(pd.to_numeric, errors='ignore')
        reStr = '^(?P<PLAYER>.+?), (?P<TEAM>\w+)\xa0(?P<POS>.+?)' \
                '(?P<DTD>$|\xa0\xa0DTD$)'
        df = df.join(df['PLAYER, TEAM POS'].str.extract(reStr, expand=True))
        df.drop('PLAYER, TEAM POS', axis=1, inplace=True)
        df['POS'] = df['POS'].apply(lambda x: x.split(', '))
        # Drop extra columns
        df = df.select(lambda x: not re.search('Unnamed: \d+', x), axis=1)
        return df

    def _downloadActiveStatsTable(self, teamId, batter=True):
        """ Download team "Active Stats" page.
            Input: teamId int, batter bool
            Output: team active stats dataframe
        """
        assert str(teamId) in self.teamDict
        teamName = self.teamDict[teamId]
        teamId = ('teamId', teamId)
        activeStatsUrl = ('http://games.espn.com/flb/activestats?' +
                          urlencode((self.leagueId, self.seasonId, teamId)))
        if batter:
            html = self._getHTML(activeStatsUrl, login=self.login)
        else:
            html = self._getHTML(activeStatsUrl + '&filter=2',
                                 login=self.login)
        htmlStr = (tostring(html.xpath(
                   '//table[@class="playerTableTable tableBody"]')[0]))
        dfTable = pd.read_html(htmlStr, header=1)[0]
        df = self._formatActiveStatsTable(dfTable)
        df['MANAGER'] = teamName
        cols = df.columns.tolist()
        return df[[cols[-1]] + cols[-5:-1] + cols[:-5]]

    def _formatStandingsTable(self, df, columns):
        """ Format standings table to dataframe
            Input: html str, roto bool
            Output: standings table dataframe
        """
        df.columns = columns
        df.drop(df[df.iloc[:, 0].isnull()].index, inplace=True)
        df = df.select(lambda x: not re.search('1\d', str(x)), axis=1)
        return df

    def _parseHeaders(self, table):
        """ Reorganize the multi-level headers to a single column that
            corresponds to the table data. Specifically tailored to ESPN's
            tables so small changes may really break this function.
        """
        head = table.xpath('.//tr[@class="tableHead"]|'
                           './/td[@class="tableHead"]')[0].text
        subHeads = table.xpath('.//tr[@class="tableSubHead"]')
        assert len(subHeads) <= 2  # Haven't seen more than two subHeads
        noname = 10
        if len(subHeads) == 2:
            # Stats tables usually have two header rows
            for idx, subHead in enumerate(subHeads):
                subHeadRow = []
                for td in subHead.xpath('.//td'):
                    if td.xpath('.//text()') == []:
                        # These are padding cells, we will remove them later
                        subHeadRow += [noname]
                        noname += 1
                    elif 'colspan' in td.attrib:
                        # These are unnecessary titles, we will remove them
                        # later
                        subHeadRow += (int(td.attrib['colspan']) *
                                       [noname])
                        noname += 1
                    else:
                        # These are the columns we want, sometimes the text
                        # is broken up.
                        subHeadRow += [' '.join(td.xpath('.//text()'))]
                if idx == 0:
                    subHead1 = subHeadRow
                if idx == 1:
                    # Create single-level column index by combining the two
                    # subheads.
                    n = len(subHead1) - 2 - len(subHeadRow)
                    columns = subHead1[:2] + subHeadRow + subHead1[-n:]
        else:
            # Standings tables usually have one header row, much simpler
            subHead = [x.xpath('.//text()') for x in subHeads[0].
                       xpath('.//td')]
            columns = [name for lst in subHead for name in lst]
        return head, columns

    def _downloadStandingsTable(self):
        """ Download league official "Standings" table. There are two tables
            within the page, roto and season stats.
            Input: roto bool
            Output: league standings dataframe
        """
        standingsUrl = ('http://games.espn.com/flb/standings?view=official&' +
                        urlencode((self.leagueId, self.seasonId)))
        html = self._getHTML(standingsUrl, login=self.login)
        tables = html.xpath('//table[@class="tableBody"]')
        dfs = []
        for table in tables:
            head, columns = self._parseHeaders(table)
            df = pd.read_html(tostring(table), skiprows=2)[0]
            df.name = head
            dfs.append(self._formatStandingsTable(df, columns))
        return dfs

    def getLeagueActiveStatsTable(self, batter=True):
        """ Return league active stats dataframe
        """
        activeTable = pd.DataFrame()
        for teamId in self.teamDict:
            df = self._downloadActiveStatsTable(teamId, batter=batter)
            activeTable = pd.concat([activeTable, df])
        return activeTable

    def getLeagueDraftTable(self):
        """ Return league auction results dataframe.
        """
        return self._downloadDraftTable()

    def getStandingsTable(self):
        """ Return league standings dataframe.
            Input: roto bool
            Output: standings dataframe
        """
        return self._downloadStandingsTable()


class Team(League):
    """ Represents team specific data tables.
        Parameters
        ----------
        leagueId: league id number str or int
        seasonId: season year str or int
        teamId: team id number str or int
        driver: if the league is password protected, you will need to pass a
        selenium webdriver in order to login to ESPN.
    """
    def __init__(self, leagueId, seasonId, teamId, login=None):
        super(Team, self).__init__(leagueId, seasonId, login=login)
        self.id = str(teamId)
        self.teamId = ('teamId', str(teamId))
        self.teamUrl = ('http://games.espn.com/flb/clubhouse?' + urlencode(
                        (self.leagueId, self.seasonId, self.teamId)))
        self.name = self.teamDict[self.id]

    def getActiveStatsTable(self, batter=True):
        """ Dataframe of team's active stats page. Choose between batter
            stats or pitcher stats.
            Input: batter bool
            Output: active stats dataframe
        """
        return self._downloadActiveStatsTable(self.id, batter=batter)

    def getDraftTable(self):
        """ Return team auction results
        """
        return self._downloadDraftTable(teamId=self.id)

    def _formatTransactionTable(self, htmlStr, tds):
        """ Format transaction tables. In order to properly parse text in
            Date and Detail columns, we need to parse HTML outside of pandas.
            Input: htmlStr str and tds xpath objects
            Output: transaction table dataframe
        """
        df = pd.read_html(htmlStr, header=1)[0]
        dates = [' '.join(i.itertext()) for i in tds[::4]]
        df['DATE'] = dates
        details = [' '.join(i.itertext()).replace('  ', ' ').replace(' ,', ',')
                   for i in tds[2::4]]
        df['DETAIL'] = details
        addDropKey = u'Transaction\xa0\xa0Add/Drop'
        addDropStr = '(\w+) dropped (.+?), \w+ \w+ to (Waivers|Free Agency)'\
                     '|(\w+) added (.+?), \w+ \w+ from (Waivers|Free Agency)'
        addDrop = pd.Series(df[df['TYPE'].str.match(addDropKey)]['DETAIL'].str.
                            findall(addDropStr))
        addDrop = addDrop.apply(lambda x: [x[0][:3], x[1][:3:-1]])
        addKey = u'Transaction\xa0\xa0Add'
        addStr = '(\w+) added (.+?), \w+ \w+ from (Waivers|Free Agency)'
        add = pd.Series(df[df['TYPE'].str.match(addKey)]['DETAIL'].str.
                        findall(addStr))
        add = add.apply(lambda x: [x[0][::-1]])
        dropKey = u'Transaction\xa0\xa0Drop'
        dropStr = '(\w+) dropped (.+?), \w+ \w+ to (Waivers|Free Agency)'
        drop = pd.Series(df[df['TYPE'].str.match(dropKey)]['DETAIL'].str.
                         findall(dropStr))
        tradeKey = u'Transaction\xa0\xa0Trade Processed'
        tradeStr = '(\w+) traded (.+?), \w+ \w+ to (\w+)'
        trade = pd.Series(df[df['TYPE'].str.match(tradeKey)]['DETAIL'].str.
                          findall(tradeStr))
        transactions = pd.concat([addDrop, add, drop, trade])
        transactions.name = 'TRANSACTION'
        df = df.join(transactions)
        return df

    def _downloadTransactionTable(self, startDate, endDate):
        start = ('startDate', startDate.strftime('%Y%m%d'))
        end = ('endDate', endDate.strftime('%Y%m%d'))
        activity = ('activityType', '2')
        transactionUrl = ('http://games.espn.com/flb/recentactivity?' +
                          urlencode((self.leagueId, self.seasonId, self.teamId,
                                    activity, start, end)))
        html = self._getHTML(transactionUrl, login=self.login)
        htmlStr = tostring(html.xpath('//table[@class="tableBody"]')[0])
        tds = html.xpath('//tr[not(@class="tableSubHead")]/td'
                         '[not(@class="tableHead")]')[1:]
        df = self._formatTransactionTable(htmlStr, tds)
        return df

    def getTransactionTable(self, startDate, endDate):
        """ Dataframe of team's transactions. Adds a new column 'TRANSACTION'
            which is a list of length 3 tuples used to describe adds, drops
            and trades: (FROM, PLAYER, TO).
            Input: startDate datetime object, endDate datetime object
            Output: transaction dataframe.
        """
        return self._downloadTransactionTable(startDate, endDate)


class Login():
    """ Logging in to ESPN requires selenium and a webdriver object, ideally
        PhantomJS. See: http://www.seleniumhq.org/projects/webdriver/ for
        info on how to instantiate a webdriver.
        Parameters
        ----------
        login: (username, password) tuple
        driver: Selenium web driver
    """
    def __init__(self, login, driver):
        self.signInUrl = 'http://games.espn.go.com/flb/signin'
        if isinstance(login, tuple):
            self.login = login
        else:
            raise TypeError('login must be (login, pw) tuple')
        self.driver = self._login(login, driver)
        self.lxml = (etree.fromstring(self.driver.page_source,
                     etree.HTMLParser()).getroottree())

    def _login(self, login, driver):
        import time
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        driver.get(self.signInUrl)
        WebDriverWait(driver, 1000).until(EC.presence_of_all_elements_located(
                      (By.XPATH, "(//iframe)")))
        frm = driver.find_element_by_xpath('//iframe[@name="disneyid-iframe"]')
        driver.switch_to_frame(frm)
        time.sleep(4)
        driver.find_element_by_xpath("(//input)[1]").send_keys(login[0])
        driver.find_element_by_xpath("(//input)[2]").send_keys(login[1])
        driver.find_element_by_xpath("//button").click()
        driver.switch_to_default_content()
        return driver

    def xpath(self, path):
        return self.lxml.xpath(path)

    def get(self, url):
        self.driver.get(url)
        self.lxml = (etree.fromstring(self.driver.page_source,
                     etree.HTMLParser()).getroottree())
