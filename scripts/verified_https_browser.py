"""Temporary test transport: actual public responses through verified system TLS.

Used only when managed Chromium lacks the proxy CA. This does not validate
Chromium's native TLS path, disable TLS checks, or serve a product backend.
"""
from contextlib import contextmanager
import hashlib
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from playwright.sync_api import Browser

@contextmanager
def verified_public_transport(prefix):
    prefix=prefix.rstrip('/')+'/';received=[]
    original_context,original_page=Browser.new_context,Browser.new_page
    def bridge(route):
        url=route.request.url
        assert url.startswith(prefix) and route.request.method=='GET'
        request=Request(url,headers={'Accept-Encoding':'identity','Cache-Control':'no-cache','User-Agent':'C-public-browser-verifier-v3'})
        try:response=urlopen(request,timeout=30)
        except HTTPError as e:response=e
        with response:
            body=response.read(8*1024*1024+1);assert len(body)<=8*1024*1024
            assert response.headers.get('Content-Encoding','identity') in ['identity','']
            headers={k:v for k,v in response.headers.items() if k.lower() not in ['transfer-encoding','content-length','content-encoding']}
            status=response.status
        received.append(dict(path=url[len(prefix):],status=status,bytes=len(body),SHA256=hashlib.sha256(body).hexdigest(),TLS_verified=True))
        route.fulfill(status=status,headers=headers,body=body)
    def context(self,*args,**kwargs):
        c=original_context(self,*args,**kwargs);c.route(prefix+'**',bridge);return c
    def page(self,**kwargs):return context(self,**kwargs).new_page()
    Browser.new_context=context;Browser.new_page=page
    try:yield received
    finally:Browser.new_context=original_context;Browser.new_page=original_page
