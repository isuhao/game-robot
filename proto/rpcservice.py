# /usr/bin/python2
# -*- coding: utf-8 -*-
import logging, time, struct
from proto import proto
import gevent
from gevent import socket
from gevent.queue import Queue
from gevent.event import AsyncResult
import socket

from google.protobuf import text_format


class RpcService(object):
    SESSION_ID = 1
    def __init__(self, addr):
        self.hub  = gevent.get_hub()
        self.addr = addr
        self.sock = None

        self.time_diff   = 0

        self.write_queue = Queue()
        self.write_tr    = None

        self.read_queue  = Queue()
        self.read_tr     = None
        self.dispatch_tr = None

        self._sessions = {}
        self.handlers = {}

    def _start(self):
        if self.sock:
            return

        # sock = util.RC4Conn(self.addr)
        # sock.connect()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(self.addr)

        self.sock        = sock
        self.read_tr     = gevent.spawn(self._read)
        self.write_tr    = gevent.spawn(self._write)
        self.dispatch_tr = gevent.spawn(self._dispatch)
        return True

    def set_timestamp(self, timestamp):
        self.time_diff = timestamp - int(time.time())

    def timestamp(self):
        return int(time.time()) + self.time_diff

    def stop(self):
        gevent.spawn(self._stop)

    def _stop(self):
        while True:
            gevent.sleep(1)
            if not self.write_queue.empty():
                continue

            if not self.read_queue.empty():
                continue

            gevent.kill(self.write_tr)
            gevent.kill(self.read_tr)
            gevent.kill(self.dispatch_tr)
            self.sock.close()
            break

    def _write(self):
        while True:
            data = self.write_queue.get()
            try:
                self.sock.sendall(data)
            except socket.error, e:
                logging.info("write socket failed:%s" % str(e))
                break

    def _read(self):
        left = ""
        while True:
            try:
                buf = self.sock.recv(4*1024)
                if not buf:
                    logging.info("client disconnected, %s:%s" % self.addr)
                    break
            except socket.error, e:
                logging.info("read socket failed:%s" % str(e))
                break

            left = left + buf
            while True:
                if len(left) < 2:
                   break 

                plen, = struct.unpack('!H', left[:2])
                if len(left) < plen + 2:
                   break 

                data = left[2:plen+2]
                left = left[plen+2:]
                self.read_queue.put(data)

    def _dispatch(self):
        while True:
            data = self.read_queue.get()
            p = proto.dispatch(data)
            session   = p["session"]
            msg    =    p["msg"]

            if p["type"] == "REQUEST":
                protoname = p["proto"]
                cb = self.handlers[protoname]
                resp = cb(msg)
                if session:
                    # rpc call
                    pack = proto.response(protoname, resp, session)
                    self._send(pack)
            else:
                # response
                ev = self._sessions[session]
                del self._sessions[session]
                ev.set(msg)

    def _get_session(self):
        cls = type(self)
        if cls.SESSION_ID > 100000000:
            cls.SESSION_ID = 1
        cls.SESSION_ID += 1
        return cls.SESSION_ID

    def _send(self, data):
        self.write_queue.put(struct.pack("!H", len(data)) + data)

    def invoke(self, protoname, msg):
        pack = proto.request(protoname, msg)
        self._send(pack)

    def call(self, protoname, msg):
        session = self._get_session()
        pack = proto.request(protoname, msg, session)
        ev = AsyncResult()
        self._sessions[session] = ev
        self._send(pack)
        return ev.get()

    def register(self, protoname, func):
        self.handlers[protoname] = func
