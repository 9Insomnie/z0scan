#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# w8ay 2019/6/28
# JiuZero 2025/7/28

import copy
import logging

import ssl, random
from urllib.parse import urlparse

from requests.cookies import RequestsCookieJar
from requests.models import Request
from requests.sessions import Session
from requests.sessions import merge_setting, merge_cookies
from requests.utils import get_encodings_from_content
from urllib3 import disable_warnings
from urllib.parse import quote
from lib.core.data import conf, KB
from lib.core.red import gredis
from lib.core.common import gethostportfromurl
from lib.core.block_info import block_count


def patch_all():
    disable_warnings()
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    ssl._create_default_https_context = ssl._create_unverified_context
    Session.request = session_request


def session_request(self, method, url,
                    params=None, data=None, headers=None, cookies=None, files=None, auth=None,
                    timeout=None,
                    allow_redirects=True, proxies=None, hooks=None, stream=None, verify=False, cert=None, json=None):
    h, p = gethostportfromurl(url)
    block = block_count(h, p)
    if block.is_block():
        return None
    # Create the Request.
    merged_cookies = merge_cookies(merge_cookies(RequestsCookieJar(), self.cookies),
                                   cookies)
    default_header = {
        "User-Agent": conf.agent,
        "Connection": "close"
    }
    params=params or ""
    def urlencode(s, chars_to_encode="!@#$^&*()=[]{}|;:'\",<>?. \\"):
        if '%' in s:
            return s
        result = []
        for char in s:
            if char in chars_to_encode:
                result.append(quote(char))
            else:
                result.append(char)
        return "".join(result)
    if isinstance(params, dict):
        params = "?" + "&".join(f"{k}={urlencode(v)}" for k, v in params.items())
    req = Request(
        method=method.upper(),
        url=url,
        headers=merge_setting(headers, default_header),
        files=files,
        data=data or {},
        json=json,
        # params=params or {},
        auth=auth,
        cookies=merged_cookies,
        hooks=hooks,
    )
    prep = self.prepare_request(req)
    prep.url += params

    raw = ''
    p = urlparse(url)
    _headers = copy.deepcopy(prep.headers)
    if "Host" not in _headers:
        _headers["Host"] = p.netloc
    if prep.body:
        body = prep.body.decode('utf-8') if isinstance(prep.body, bytes) else prep.body
        raw = "{}\n{}\n\n{}\n\n".format(
            prep.method + ' ' + prep.url + ' HTTP/1.1',
            '\n'.join('{}: {}'.format(k, v) for k, v in _headers.items()),
            body)
    else:
        raw = "{}\n{}\n\n".format(
            prep.method + ' ' + prep.url + ' HTTP/1.1',
            '\n'.join('{}: {}'.format(k, v) for k, v in _headers.items()))

    proxies = proxies or {}
    if conf.get("proxies") and not proxies:
        proxies = conf["proxies"]
        p = random.choice(proxies.keys())
        _tmp_str = f"{p}://" + random.choice(proxies[p])
        _tmp_proxy = {
            "http": _tmp_str,
            "https": _tmp_str
        }
        proxies = _tmp_proxy
    # prep.url = prep.url.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
    settings = self.merge_environment_settings(
        prep.url, proxies, stream, verify, cert
    )

    # Send the request.
    send_kwargs = {
        'timeout': timeout or conf["timeout"],
        'allow_redirects': allow_redirects,
    }
    send_kwargs.update(settings)

    resp = self.send(prep, **send_kwargs)
    KB["request"] += 1
    if resp != None:
        block.push_result_status(0)
        """
        if scan_set.get("search_open", False):
            s = searchmsg(r)
            s.verify()
        """
    else:
        block.push_result_status(1)
        if conf.redis:
            red = gredis()
            red.hincrby("count", "request_fail", amount=1)
        KB["request_fail"] += 1
        
    if resp.encoding == 'ISO-8859-1':
        encodings = get_encodings_from_content(resp.text)
        if encodings:
            encoding = encodings[0]
        else:
            encoding = resp.apparent_encoding

        resp.encoding = encoding

    setattr(resp, 'reqinfo', raw)
    return resp
