#!/usr/bin/env python

__author__ = "Gawen Arab"
__copyright__ = "Copyright 2012, Gawen Arab"
__credits__ = ["Gawen Arab"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Gawen Arab"
__email__ = "gawen@forgetbox.com"
__status__ = "Beta"

import BeautifulSoup
import datetime
import email.utils
import errno
import functools
import fuse
import httplib
import logging
import optparse
import os
import sys
import socket
import stat
import threading
import time
import urllib
import urlparse

class TimeoutDictionary(object):
    def __init__(self, timeout):
        super(TimeoutDictionary, self).__init__()

        self.timeout = timeout
        self.d = {}

    def __getitem__(self, k):
        v = self.d[k]

        if time.time() - v[0] > self.timeout:
            raise KeyError(k)
        
        return v[1]

    def __setitem__(self, k, v):
        self.d[k] = [time.time(), v]

    def __delitem__(self, k):
        del self.d[k]

    def get(self, k, default = None):
        try:
            return self[k]

        except KeyError:
            return None

    def iterkeys(self):
        for k, v in self.d.iteritems():
            if time.time() - v[0] > self.timeout:
                continue

            yield k

    __iter__ = iterkeys

    def iteritems(self):
        for k in self.iterkeys():
            yield (k, self[k])

    def itervalues(self):
        for k in self.iterkeys():
            yield self[k]

    def __len__(self):
        return len(list(self))

    def __contains__(self, k):
        return k in list(self)

def func_cache(f):
    @functools.wraps(f)
    def wrapper(self, path, *kargs, **kwargs):
        if not hasattr(f, "_cache"):
            f._cache = TimeoutDictionary(self.timeout)

        with self.lock:
            r = f._cache.get(path, None)

        if r is not None:
            if isinstance(r, Exception):
                raise r

            return r

        try:
            r = f(self, path, *kargs, **kwargs)

        except OSError, e:
            with self.lock:
                f._cache[path] = e

            raise e
        
        else:
            with self.lock:
                f._cache[path] = r
            
            return r

    return wrapper

class ApacheFuse(fuse.LoggingMixIn, fuse.Operations):
    def __init__(self, base_url, timeout = None):
        timeout = timeout if timeout is not None else 60

        self.timeout = timeout

        if not base_url.endswith("/"):
            base_url += "/"

        self.base_url_str = base_url
        self.base_url = urlparse.urlparse(base_url)
        
        self.lock = threading.Lock()

        assert self.base_url.scheme in ("http", "https", )

        self.local = threading.local()

    def create_connection(self):
        http_connection_cls = {
            "http": httplib.HTTPConnection,
            "https": httplib.HTTPSConnection,
        }[self.base_url.scheme]

        http_connection = http_connection_cls(
            self.base_url.hostname,
            port = self.base_url.port,
        )

        return http_connection

    @property
    def connection(self):
        if not hasattr(self.local, "connection"):
            self.local.connection = self.create_connection()

        return self.local.connection

    def request(self, method, path, headers = None):
        headers = headers if headers is not None else {}

        base_path = self.base_url.path
        if base_path.endswith("/"):
            base_path = base_path[:-1]

        path = base_path + path

        try:
            self.connection.request(method, path, headers = headers)
            response = self.connection.getresponse()

        except socket.gaierror:
            raise OSError(errno.ECONNREFUSED, os.strerror(errno.ECONNREFUSED))

        if response.status == 404:
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT))

        if response.status in (301, 302, ):
            # Flush
            response.read()

            location = response.getheader("Location")

            if not location.startswith(self.base_url_str):
                raise OSError(errno.ENOENT, os.strerror(errno.ENOENT))

            location = location[len(self.base_url_str):]
            
            return self.request(method, "/" + location, headers)

        return path, response

    @func_cache
    def readdir(self, path, fh = None):
        path, response = self.request("GET", urllib.quote(path))
        response = response.read()
        response = BeautifulSoup.BeautifulSoup(response)
        
        if response.pre:
            response = response.pre

            listdir = []
            for a in response.findAll("a", recursive = False):
                if a["href"] != a.text:
                    continue
                
                path = a.text

                if path.endswith("/"):
                    path = path[:-1]

                listdir.append(path)

            return listdir

        elif response.table:
            
            response = response.table
            
            # Get meta
            def get_meta_list():
                r = {}
                for i, meta in enumerate(response.tr.findAll("th")):
                    meta = meta.a

                    if meta:
                        meta = str(meta.text).lower()

                    r[i] = meta
                
                return r

            meta_list = get_meta_list()
            
            def get_meta(file_dom, meta_list):
                r = {}
                for i, m in enumerate(file_dom):
                    meta_title = meta_list[i]
                    
                    if meta_title is None:
                        continue

                    r[meta_title] = m

                return r

            listdir = []
            for file_dom in response.findAll("tr", recursive = False):
                file_dom = file_dom.findAll("td", recursive = False)
                
                if len(file_dom) != len(meta_list):
                    continue

                file_meta = get_meta(file_dom, meta_list)
                file_path = file_meta["name"].a["href"]
                file_name = file_meta["name"].text
                if file_name == "Parent Directory":
                    continue

                file_path = path + file_path

                if file_name.endswith("/"):
                    file_name = file_name[:-1]

                listdir.append(file_name)

            return listdir

    @func_cache 
    def getattr(self, path, fh = None):
        path, response = self.request("HEAD", urllib.quote(path))

        st = {}

        st["st_mode"] = 0
        if path.endswith("/"):
            st["st_mode"] |= stat.S_IFDIR
        
            st["st_mode"] |= stat.S_IXUSR
            st["st_mode"] |= stat.S_IXGRP

        else:
            st["st_mode"] |= stat.S_IFREG

        st["st_mode"] |= stat.S_IRUSR
        st["st_mode"] |= stat.S_IRGRP

        # Parse data
        date = response.getheader("Date")
        if date is not None:
            amc_time = email.utils.parsedate(date)
            amc_time = time.mktime(amc_time)
            amc_time = int(amc_time)

            st["st_atime"] = st["st_mtime"] = st["st_ctime"] = amc_time

        content_length = response.getheader("Content-Length")
        if content_length is not None:
            content_length = int(content_length)
            st["st_size"] = content_length

        st["st_gid"] = 1000
        st["st_uid"] = 1000
        st["st_nlink"] = 1

        return st

    def read(self, path, size, offset, fh = None):
        start = offset
        end = offset + size - 1
        
        headers = {
            "Range": "bytes=%d-%d" % (start, end, )
        }

        path, response = self.request("GET", urllib.quote(path), headers = headers)

        if path.endswith("/"):
            raise OSError(errno.EISDIR, os.strerror(errno.EISDIR))

        buf = response.read()

        return buf

def main():
    parser = optparse.OptionParser()
    parser.add_option("-v", "--verbose", action = "store_true", default = False)
    parser.add_option("-f", "--foreground", action = "store_true", default = False)
    options, arguments = parser.parse_args()

    if options.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.basicConfig()

    if len(arguments) != 2:
        parser.print_help()
        return -1

    f = fuse.FUSE(ApacheFuse(arguments[0]), arguments[1],
        foreground = options.foreground,
        encoding = "latin-1",
    )

if __name__ == "__main__":
    sys.exit(main())
