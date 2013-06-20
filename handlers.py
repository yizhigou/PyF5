#coding:utf-8
import base64
import os
import json
import time
import cPickle
from StringIO import StringIO

from tornado.web import StaticFileHandler, RequestHandler, asynchronous, HTTPError

from utils import app_path, get_rel_path, we_are_frozen
from zfs import ZipFileSystem
from assets import assets_zip64


zfs = None
if we_are_frozen():
    assets_zip_file = StringIO(base64.decodestring(assets_zip64))
    zfs = ZipFileSystem(assets_zip_file)


class StaticFileHandlerWithoutCache(StaticFileHandler):
    def should_return_304(self):
        return False


class AssetsHandler(StaticFileHandlerWithoutCache):
    def initialize(self, path, default_name=None):
        StaticFileHandlerWithoutCache.initialize(self, path, default_name)
        self.rel_path = get_rel_path(self.request.path, '/_f5/')

    @classmethod
    def get_content(cls, abspath, start=None, end=None):
        rel_path = get_rel_path(abspath, app_path())
        return zfs.read(rel_path)

    def get_content_size(self):
        return zfs.file_size(self.rel_path) or 0

    def get_modified_time(self):
        return int(zfs.modified_at(self.rel_path)) or 0

    def validate_absolute_path(self, root, absolute_path):
        if not zfs.file_size(self.rel_path):
            raise HTTPError(404)
        return absolute_path


class HtmlFileHandler(StaticFileHandlerWithoutCache):
    SCRIPT_AND_END_OF_BODY = '<script id="_f5_script" src="_f5/js/reloader.js"></script>\n</body>'
    @classmethod
    def get_content(cls, abspath, start=None, end=None):
        html = open(abspath, 'r').read()
        html = html.replace('</body>', cls.SCRIPT_AND_END_OF_BODY)
        return html

    def get_content_size(self):
        size = StaticFileHandlerWithoutCache.get_content_size(self)
        size = size - len('</body>') + len(self.__class__.SCRIPT_AND_END_OF_BODY)
        return size


class ChangeRequestHandler(RequestHandler):
    def initialize(self, refresher):
        self.refresher = refresher
        self.refresher.change_request_handlers.add(self)

        self.callback = self.get_argument('callback', '_F5.handleChanges')
        self.max_pending_time = 20
        self.query_time = time.time()

        deadline = time.time() + self.max_pending_time
        self.timeout = self.refresher._loop.add_timeout(deadline, lambda: self.return_changes([]))

    @asynchronous
    def get(self):
        pass

    def return_changes(self, changes):
        ret = {
            'status': 'ok',
            'changes': [change._asdict() for change in changes],
        }
        ret = '%s(%s);' % (self.callback, json.dumps(ret))
        print ret
        self.write(ret)
        self.finish()
        self.refresher._loop.remove_timeout(self.timeout)
        self.refresher.change_request_handlers.remove(self)

    def post(self):
        pass


if __name__ == '__main__':
    import base64
    import cPickle
    from zfs import ZipFileSystem
    vfs_dict = ZipFileSystem.make_VFS_dict('assets')
    raw_data = cPickle.dumps(vfs_dict)
    wf = open('assets.py', 'w+')
    wf.write('pickle_base64 = """%s"""' % base64.encodestring(raw_data))
    wf.close()

    from assets import pickle_base64
    data = cPickle.loads(base64.decodestring(pickle_base64))
    print data