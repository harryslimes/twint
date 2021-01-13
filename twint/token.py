import re
import time
import aiohttp
import asyncio
from async_timeout import timeout


import requests
from . import get
import logging as logme


class TokenExpiryException(Exception):
    def __init__(self, msg):
        super().__init__(msg)

        
class RefreshTokenException(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        

class Token:
    async def Request(self,_url,session, connector=None, params=None, headers=None):
        logme.debug(__name__ + ':Request:Connector')
        return await self.Response(session, _url, params)


    async def Response(self,session, _url, params=None):
        logme.debug(__name__ + ':Response')
        httpproxy = None
        with timeout(120):
            async with session.get(_url, ssl=True, params=params, proxy=httpproxy) as response:
                resp = await response.text()
                if response.status == 429:  # 429 implies Too many requests i.e. Rate Limit Exceeded
                    raise TokenExpiryException(loads(resp)['errors'][0]['message'])
                return resp


    def __init__(self, config):
        self.config = config
        self._retries = 10
        self._timeout = 2
        self.url = 'https://twitter.com'

    async def _request(self,_connector):
        async with aiohttp.ClientSession(connector=_connector,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0'}) as session:
            for attempt in range(self._retries + 1):
                # The request is newly prepared on each retry because of potential cookie updates.
                logme.debug(f'Retrieving {self.url}')
                try:
                    r = await self.Request(self.url,session)
                except requests.exceptions.RequestException as exc:
                    if attempt < self._retries:
                        retrying = ', retrying'
                        level = logme.WARNING
                    else:
                        retrying = ''
                        level = logme.ERROR
                    logme.log(level, f'Error retrieving {self.url}: {exc!r}{retrying}')
                else:
                    success, msg = (True, None)
                    msg = f': {msg}' if msg else ''

                    if success:
                        logme.debug(f'{self.url} retrieved successfully{msg}')
                        match = re.search(r'\("gt=(\d+);', r)
                        if match:
                            logme.debug('Found guest token in HTML')
                            self.config.Guest_token = str(match.group(1))
                            return r

                if attempt < self._retries:
                    # TODO : might wanna tweak this back-off timer
                    sleep_time = 2.0 * 2 ** attempt
                    print(f'Waiting {sleep_time:.0f} seconds')
                    logme.info(f'Waiting {sleep_time:.0f} seconds')
                    await asyncio.sleep(sleep_time)
            else:
                msg = f'{self._retries + 1} requests to {self.url} failed, giving up.'
                logme.fatal(msg)
                self.config.Guest_token = None
                raise RefreshTokenException(msg)

    async def refresh(self,connector):
        logme.debug('Retrieving guest token')
        self.config.Guest_token = None
        await self._request(connector)
        if self.config.Guest_token is None:
            raise RefreshTokenException('Could not find the Guest token in HTML')
        