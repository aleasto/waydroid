import logging
import os
import threading
import tools.config
import tools.helpers.ipc
import dbus
from tools.interfaces import IAppMonitor

stopping = False

def start(args):
    def on_open(package_name):
        try:
            tools.helpers.ipc.DBusAppService(package_name).OnOpen()
        except dbus.DBusException:
            pass

    def on_close(package_name):
        try:
            tools.helpers.ipc.DBusAppService(package_name).OnClose()
        except dbus.DBusException:
            pass

    def service_thread():
        while not stopping:
            IAppMonitor.add_service(args, on_open, on_close)

    global stopping
    stopping = False
    args.app_monitor = threading.Thread(target=service_thread)
    args.app_monitor.start()

def stop(args):
    global stopping
    stopping = True

    def close_action(obj):
        try:
            obj.OnClose(dbus_interface="id.waydro.AppMonitor")
        except dbus.DBusException:
            pass

    for_all_apps(close_action)

    try:
        if args.appMonitorLoop:
            args.appMonitorLoop.quit()
    except AttributeError:
        logging.debug("UserMonitor service is not even started")

def for_all_apps(action):
    try:
        bus = dbus.SessionBus()
        for service in bus.list_names():
            if service.startswith("id.waydro.App."):
                action(bus.get_object(service, "/Monitor"))

    except dbus.DBusException:
        pass
