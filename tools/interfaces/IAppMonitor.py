import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "vendor.waydroid.appmonitor.IAppMonitor"
SERVICE_NAME = "waydroidappmonitor"

TRANSACTION_open = 1
TRANSACTION_close = 2

def add_service(args, on_open, on_close):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.VNDBINDER_DRIVER, args.VNDBINDER_PROTOCOL, args.VNDBINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.VNDBINDER_DRIVER)

    def response_handler(req, code, flags):
        logging.debug(
            "{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader = req.init_reader()
        local_response = response.new_reply()
        if code == TRANSACTION_open:
            package_name = reader.read_string16()
            on_open(package_name)
            local_response.append_int32(0)
        if code == TRANSACTION_close:
            package_name = reader.read_string16()
            on_close(package_name)
            local_response.append_int32(0)

        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.appMonitorLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.appMonitorLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.appMonitorLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))

