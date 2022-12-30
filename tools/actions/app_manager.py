# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import sys
import shutil
import time
import threading
import subprocess
import tools.config
import tools.helpers.props
import tools.helpers.ipc
from tools.interfaces import IPlatform
from tools.interfaces import IStatusBarService
import dbus
import dbus.exceptions
from gi.repository import GLib

def install(args):
    try:
        tools.helpers.ipc.DBusSessionService()

        cm = tools.helpers.ipc.DBusContainerService()
        session = cm.GetSession()
        if session["state"] == "FROZEN":
            cm.Unfreeze()

        tmp_dir = tools.config.session_defaults["waydroid_data"] + "/waydroid_tmp"
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        shutil.copyfile(args.PACKAGE, tmp_dir + "/base.apk")
        platformService = IPlatform.get_service(args)
        if platformService:
            platformService.installApp("/data/waydroid_tmp/base.apk")
        os.remove(tmp_dir + "/base.apk")

        if session["state"] == "FROZEN":
            cm.Freeze()
    except (dbus.DBusException, KeyError):
        logging.error("WayDroid session is stopped")

def remove(args):
    try:
        tools.helpers.ipc.DBusSessionService()

        cm = tools.helpers.ipc.DBusContainerService()
        session = cm.GetSession()
        if session["state"] == "FROZEN":
            cm.Unfreeze()

        platformService = IPlatform.get_service(args)
        if platformService:
            ret = platformService.removeApp(args.PACKAGE)
            if ret != 0:
                logging.error("Failed to uninstall package: {}".format(args.PACKAGE))

        if session["state"] == "FROZEN":
            cm.Freeze()
    except dbus.DBusException:
        logging.error("WayDroid session is stopped")

def maybeLaunchLater(args, launchNow, pkg):
    try:
        tools.helpers.ipc.DBusSessionService()
        try:
            tools.helpers.ipc.DBusContainerService().Unfreeze()
        except:
            logging.error("Failed to unfreeze container. Trying to launch anyways...")

        if not pkg:
            launchNow()
            return

        try:
            name = dbus.service.BusName("id.waydro.App." + pkg, dbus.SessionBus(), do_not_queue=True)
            launch_thread = threading.Thread(target=launchNow)
            launch_thread.daemon = True
            launch_thread.start()
            monitor_service(args)
        except dbus.exceptions.NameExistsException:
            logging.info("App %s is already launched" % pkg)
    except dbus.DBusException:
        # Spawn a new process for the session. Can't use multiprocessing with GLib.MainLoop
        # TODO: Maybe use dbus activation instead
        if os.environ.get("WAYDROID_NO_APP_MONITOR") == "1":
            logging.info("Starting waydroid session")
            tools.actions.session_manager.start(args, launchNow)
        else:
            env = os.environ.copy()
            env["WAYDROID_NO_APP_MONITOR"] = "1"
            subprocess.Popen(sys.argv, env=env)
            if not pkg:
                return
            try:
                name = dbus.service.BusName("id.waydro.App." + pkg, dbus.SessionBus(), do_not_queue=True)
                monitor_service(args, timeout=1000) # matches the timeout of IPlatfom.get_service
            except dbus.exceptions.NameExistsException:
                pass

def launch(args):
    def justLaunch():
        platformService = IPlatform.get_service(args)
        if platformService:
            platformService.setprop("waydroid.active_apps", args.PACKAGE)
            ret = platformService.launchApp(args.PACKAGE)
            multiwin = platformService.getprop(
                "persist.waydroid.multi_windows", "false")
            if multiwin == "false":
                platformService.settingsPutString(
                    2, "policy_control", "immersive.status=*")
            else:
                platformService.settingsPutString(
                    2, "policy_control", "immersive.full=*")
        else:
            logging.error("Failed to access IPlatform service")
    maybeLaunchLater(args, justLaunch, args.PACKAGE)

def list(args):
    try:
        tools.helpers.ipc.DBusSessionService()

        cm = tools.helpers.ipc.DBusContainerService()
        session = cm.GetSession()
        if session["state"] == "FROZEN":
            cm.Unfreeze()

        platformService = IPlatform.get_service(args)
        if platformService:
            appsList = platformService.getAppsInfo()
            for app in appsList:
                print("Name: " + app["name"])
                print("packageName: " + app["packageName"])
                print("categories:")
                for cat in app["categories"]:
                    print("\t" + cat)

        if session["state"] == "FROZEN":
            cm.Freeze()
        else:
            logging.error("Failed to access IPlatform service")
    except dbus.DBusException:
        logging.error("WayDroid session is stopped")

def showFullUI(args):
    def justShow():
        platformService = IPlatform.get_service(args)
        if platformService:
            platformService.setprop("waydroid.active_apps", "Waydroid")
            platformService.settingsPutString(2, "policy_control", "null*")
            # HACK: Refresh display contents
            statusBarService = IStatusBarService.get_service(args)
            if statusBarService:
                statusBarService.expand()
                time.sleep(0.5)
                statusBarService.collapse()
    maybeLaunchLater(args, justShow, "Waydroid")

def intent(args):
    def justLaunch():
        platformService = IPlatform.get_service(args)
        if platformService:
            ret = platformService.launchIntent(args.ACTION, args.URI)
            if ret == "":
                return
            pkg = ret if ret != "android" else "Waydroid"
            platformService.setprop("waydroid.active_apps", pkg)
            multiwin = platformService.getprop(
                "persist.waydroid.multi_windows", "false")
            if multiwin == "false":
                platformService.settingsPutString(
                    2, "policy_control", "immersive.status=*")
            else:
                platformService.settingsPutString(
                    2, "policy_control", "immersive.full=*")
        else:
            logging.error("Failed to access IPlatform service")
    maybeLaunchLater(args, justLaunch, None)

def monitor_service(args, timeout=15):
    mainloop = GLib.MainLoop()
    dbus_obj = DbusAppMonitor(mainloop, dbus.SessionBus(), "/Monitor", args, timeout)
    try:
        mainloop.run()
    except KeyboardInterrupt:
        pass

class DbusAppMonitor(dbus.service.Object):
    def __init__(self, looper, bus, object_path, args, timeout):
        self.args = args
        self.looper = looper
        self.timer = GLib.timeout_add_seconds(timeout, self.on_timeout)
        dbus.service.Object.__init__(self, bus, object_path)

    @dbus.service.method("id.waydro.AppMonitor", in_signature='', out_signature='')
    def OnOpen(self):
        GLib.source_remove(self.timer)

    @dbus.service.method("id.waydro.AppMonitor", in_signature='', out_signature='')
    def OnClose(self):
        self.looper.quit()

    def on_timeout(self):
        logging.error("App didn't start in time")
        self.looper.quit()
