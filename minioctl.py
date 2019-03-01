#!/usr/bin/env python2.7
#-*- coding: utf-8 -*-

"""
Author : jiangyang
Date : 2017.03.08
Description : start or stop minio services in FusionNAS
"""

import os
import sys
import errno
import syslog
import argparse

#from argparse import RawTextHelpFormatter

from utils import exec_shell, Exp, dmsg, dwarn, derror,\
                json_load, json_store, check_process_exists

ERROR_FAILED = -1
ERROR_SUCCESS = 0

MINIO_CONF_PATH = '/opt/minio/config'

class Minio:
    def __init__(self):
        if not os.path.isdir(MINIO_CONF_PATH):
            os.makedirs(MINIO_CONF_PATH)
            return 0

    def _split_dirname(self, dirname):
        ridx = dirname.rindex('_')
        name = dirname[0:ridx]
        port = dirname[ridx+1:]

        return name,port

    def _check_exists(self, name="", port=""):
        for f in os.listdir(MINIO_CONF_PATH):
            _name,_port = self._split_dirname(f)
            if name is not None and _name == name:
                return 1

            if port is not None and _port == port:
                return 1

        return 0

    def tenant_add(self, name, password, port):
        if self._check_exists(name, port):
            raise Exp(errno.EEXIST, "name or port has been used, please check it!")

        #create tenant config directory
        dirname = "%s_%s" % (name, port)
        abs_path = "%s/%s" % (MINIO_CONF_PATH, dirname)
        os.mkdir(abs_path)

        #generate config.json
        cmd = "cp /opt/minio/config.json %s" % (abs_path)
        exec_shell(cmd, p=False)

        #modify config.json about accessKey and secretKey
        json_file = "%s/config.json" % (abs_path)
        data = json_load(json_file)
        data["credential"]["accessKey"] = name
        data["credential"]["secretKey"] = password
        json_store(data, json_file)

    def _get_full_name(self, name, is_raise=1):
        for f in os.listdir(MINIO_CONF_PATH):
            _name,_port = self._split_dirname(f)
            if name == _name:
                return f

        if is_raise:
            raise Exp(errno.ENOENT, "name:%s not exists!" % name)
        else:
            return ""

    def tenant_del(self, name):
        fname = _get_full_name(name, is_raise=0)
        if len(fname) != 0:
            cmd = "ps -ef | grep '%s ' | grep -v 'grep' | awk '{print $2}'| xargs kill -9" % (fname)
            exec_shell(cmd)
            cmd = "rm -rf %s/%s" % (MINIO_CONF_PATH, fname)
            exec_shell(cmd)
        else:
            dwarn("name:%s not exists, please check it!" % name)

    def tenant_mod(self, name, password):
        fname = _get_full_name(name)
        json_file = "%s/%s/config.json" % (MINIO_CONF_PATH, fname)
        data = json_load(json_file)
        data["credential"]["secretKey"] = password
        json_store(data, json_file)

    def tenant_list(self):
        no_tenant = True

        for f in os.listdir(MINIO_CONF_PATH):
            name,port = self._split_dirname(f)
            dmsg("\ttenant:%s\t\tport:%s" % (name, port))
            no_tenant = False

        if no_tenant:
            dmsg("\tno tenant !")

        return
        
    def _tenant_start_single(self, fname, home):
        name,port = self._split_dirname(fname)
        key = "%s/%s " % (MINIO_CONF_PATH, fname)
        if not check_process_exists(key):
            #start user
            if not os.path.isdir(home):
                os.makedirs(home)

            abs_conf_path = "%s/%s" % (MINIO_CONF_PATH, fname)
            cmd = "/opt/minio/minio server --config-dir %s --address :%s %s >/dev/null 2>&1 &" % (abs_conf_path, port, home)
            exec_shell(cmd)
            dmsg("tenant %s port %s server start OK !" % (name, port))
        else:
            dmsg("tenant %s port %s server is running !" % (name, port))

    def tenant_start(self, name=None, home=None):
        if name is not None:
            fname = self._get_full_name(name)
            self._tenant_start_single(fname, home)
        else:
            #start all tenants minio server
            if not os.path.isdir(MINIO_CONF_PATH):
                os.makedirs(MINIO_CONF_PATH)
                return

            for fname in os.listdir(MINIO_CONF_PATH):
                self._tenant_start_single(fname, home)

    def tenant_stop(self, name=""):
        if name is not None:
            #just stop the tenant minio
            fname = _get_full_name(name)
            key = "%s/%s " % (MINIO_CONF_PATH, fname)
            if not check_process_exists(key):
                dmsg("tenant %s already stopped !" % name)
            else:
                cmd = "ps -ef | grep '%s ' | grep -v grep | awk '{print $2}' | xargs kill -9" % (key)
                exec_shell(cmd, p=False)
                dmsg("tenant %s stopped ok!" % (name))
        else:
            #stop all tenants minio
            try:
                cmd = "ps -ef | grep minio | grep -v grep | awk '{print $2}' | xargs kill -9"
                exec_shell(cmd)
                dmsg("minio server stopped OK !")
            except Exception as e:
                dmsg("minio server already stopped !")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    def _tenant_add(args, minio):
        minio.tenant_add(args.name, args.password, args.port)
    parser_tenant_add = subparsers.add_parser('tenant_add', help='add a minio tenant')
    parser_tenant_add.add_argument("--name", required=True, help="tenant name")
    parser_tenant_add.add_argument("--password", required=True, help="tenant password")
    parser_tenant_add.add_argument("--port", required=True, help="port of this minio tenant")
    parser_tenant_add.set_defaults(func=_tenant_add)

    def _tenant_del(args, minio):
        minio.tenant_del(args.name)
    parser_tenant_del = subparsers.add_parser('tenant_del', help='del a minio tenant')
    parser_tenant_del.add_argument("--name", required=True, help="tenant name")
    parser_tenant_del.set_defaults(func=_tenant_del)

    def _tenant_mod(args, minio):
        minio.tenant_mod(args.name, args.password)
    parser_tenant_mod = subparsers.add_parser('tenant_mod', help='mod minio tenant info')
    parser_tenant_mod.add_argument("--name", required=True, help="tenant name")
    parser_tenant_mod.add_argument("--password", required=True, help="tenant password")
    parser_tenant_mod.set_defaults(func=_tenant_mod)

    def _tenant_list(args, minio):
        minio.tenant_list()
    parser_tenant_list = subparsers.add_parser('tenant_list', help='list minio tenants')
    parser_tenant_list.set_defaults(func=_tenant_list)

    def _tenant_start(args, minio):
        minio.tenant_start(args.name, args.home)
    parser_tenant_start = subparsers.add_parser('tenant_start', help='start minio server by tenant')
    parser_tenant_start.add_argument("--home", required=True, help="minio data directory")
    parser_tenant_start.add_argument("--name", default=None, help="tenant name")
    parser_tenant_start.set_defaults(func=_tenant_start)

    def _tenant_stop(args, minio):
        minio.tenant_stop(args.name)
    parser_tenant_stop = subparsers.add_parser('tenant_stop', help='stop minio server by tenant')
    parser_tenant_stop.add_argument("--name", default=None, help="tenant name")
    parser_tenant_stop.set_defaults(func=_tenant_stop)

    if (len(sys.argv) == 1):
        parser.print_help()
        sys.exit(-1)

    minio = Minio()
    args = parser.parse_args()
    args.func(args, minio)

