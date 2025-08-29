#!/usr/bin/env python3
# caicai 2020-06-09

import socket
import threading
import struct
import time
import binascii
from lib.core.data import conf
from lib.core.log import logger
from lib.reverse.lib import reverse_records, reverse_lock
from ldaptor.protocols import pureldap, pureber


def decode(query):
    info = ""
    try:
        info = binascii.a2b_hex(query[4:].encode()).decode()
    except Exception as ex:
        logger.warning("Decode ldap error:{} sourquery:{}".format(ex, query))
    return info


def getldappath(buff):
    berdecoder = pureldap.LDAPBERDecoderContext_TopLevel(
        inherit=pureldap.LDAPBERDecoderContext_LDAPMessage(
            fallback=pureldap.LDAPBERDecoderContext(
                fallback=pureber.BERDecoderContext()),
            inherit=pureldap.LDAPBERDecoderContext(
                fallback=pureber.BERDecoderContext())))
    # buff=b'\x30\x81\xa9\x02\x01\x02c\x81\x86\x04fAaBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n\x01\x00\n\x01\x03\x02\x01\x00\x02\x01\x00\x01\x01\x00\x87\x0bobjectClass0\x00\xa0\x1b0\x19\x04\x172.16.840.1.113730.3.4.2'
    try:
        o, bytes = pureber.berDecodeObject(
            berdecoder, buff)
        return o.value.baseObject
    except pureber.BERExceptionInsufficientData as ex:
        logger.warning("Error:{}".format(ex), origin="LDAP")
        return None


def ldap_response(client, address):
    try:
        client.settimeout(30)
        buf = client.recv(512)
        if buf.hex().startswith("300c0201"):
            send_data = b"\x30\x0c\x02\x01\x01\x61\x07\x0a\x01\x00\x04\x00\x04\x00"
            client.send(send_data)
            total = 3  # 防止socket的recv接收数据不完整
            buf1 = b""
            while total:
                buf1 += client.recv(512)
                if len(buf1) > 16:
                    break
            if buf1:
                path = getldappath(buf1).decode(errors="ignore")
                logger.debug("Client {} send {}".format(address, path), origin="LDAP")
                res = {}
                res["type"] = "ldap"
                res["client"] = address[0]
                res["query"] = path
                res["info"] = decode(path)
                res["time"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                logger.info(f"Record: {str(res)}", origin="LDAP")
                reverse_lock.acquire()
                reverse_records.append(res)
                reverse_lock.release()
                
    except Exception as ex:
        logger.warning('Run ldap error:{} address:{}'.format(ex, address))
    finally:
        client.close()


def ldap_start():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ip=conf.reverse.get("ldap_ip")
    port=int(conf.reverse.get("ldap_port"))
    sock.bind((ip, port))
    sock.listen(200)
    while True:
        client, address = sock.accept()
        thread = threading.Thread(target=ldap_response, args=(client, address))
        thread.setDaemon(True)
        thread.start()

