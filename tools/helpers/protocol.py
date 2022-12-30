from tools import helpers
import tools.config
import logging

# Call me with rootfs mounted!
def set_aidl_version(args):
    def protocol_from_api(ver):
        if ver < 28:
            binder_protocol = "aidl"
            sm_protocol =     "aidl"
        elif ver < 30:
            binder_protocol = "aidl2"
            sm_protocol =     "aidl2"
        elif ver < 31:
            binder_protocol = "aidl3"
            sm_protocol =     "aidl3"
        else:
            binder_protocol = "aidl3"
            sm_protocol =     "aidl4"
        return (binder_protocol, sm_protocol)

    cfg = tools.config.load(args)
    system_api = 0
    try:
        system_api = int(helpers.props.file_get(args,
                tools.config.defaults["rootfs"] + "/system/build.prop",
                "ro.build.version.sdk"))
    except:
        logging.error("Failed to parse android version from system.img")

    vendor_api = system_api
    try:
        vendor_api = int(helpers.props.file_get(args,
                tools.config.defaults["rootfs"] + "/vendor/build.prop",
                "ro.vendor.build.version.sdk"))
    except:
        logging.error("Failed to parse android version from system.img")

    cfg["waydroid"]["binder_protocol"], cfg["waydroid"]["service_manager_protocol"] = protocol_from_api(system_api)
    cfg["waydroid"]["vnd_binder_protocol"], cfg["waydroid"]["vnd_service_manager_protocol"] = protocol_from_api(vendor_api)

    tools.config.save(args, cfg)
