# Copyright (c) 2016, The MITRE Corporation. All rights reserved.
# See LICENSE.txt for complete terms.

import sys
import stix
import cybox
from cybox.objects.address_object import Address
from cybox.objects.uri_object import URI
from cybox.objects.file_object import File
from cybox.objects.win_registry_key_object import WinRegistryKey
from cybox.objects.process_object import Process
from cybox.objects.win_process_object import WinProcess
from cybox.objects.win_service_object import WinService
from cybox.objects.domain_name_object import DomainName
from cybox.objects.mutex_object import Mutex
from cybox.objects.network_connection_object import NetworkConnection

from elevator.utils import *
from elevator.convert_pattern import *
from elevator.vocab_mappings import *


def convert_address(add):
    if add.category == add.CAT_IPV4:
        return {"type": "ipv4-address-object", "value": add.address_value.value}
    elif add.category == add.CAT_IPV6:
        return {"type": "ipv6-address-object", "value": add.address_value.value}


def convert_uri(uri):
    return {"type": "url-object", "value": + uri.value.value}


def convert_file(file):
    first_one = True
    cybox_dict = {"type": "file-object"}
    if file.size is not None:
        if isinstance(file.size.value, list):
            error("file size window not allowed in top level observable, using first value")
            cybox_dict["size"] = int(file.size.value[0])
        else:
            cybox_dict["size"] = int(file.size)
    if file.hashes is not None:
        hashes = {}
        for h in file.hashes:
            hashes[str(h.type_).lower()] = h.simple_hash_value.value
        cybox_dict["hashes"] = hashes
    if file.file_name:
        cybox_dict["file_name"] = str(file.file_name)
    # TODO: handle path properties be generating a directory object?
    return cybox_dict


def convert_registry_key(reg_key):
    cybox_reg = {"type": "windows-registry-key"}
    if reg_key.key or reg_key.hive:
        full_key = ""
        if reg_key.hive:
            full_key += reg_key.hive.value + "\\"
        if reg_key.key:
            full_key += reg_key.key.value
        cybox_reg["key"] = full_key
    else:
        error("windows-registry-key is required to have a key property")
    if reg_key.values:
        cybox_reg["values"] = []
        for v in reg_key.values:
            reg_value = {}
            if hasattr(v, "data") and v.data:
                reg_value["data"] = str(v.data)
            if hasattr(v, "name") and v.name:
                reg_value["name"] = str(v.name)
            if hasattr(v, "datatype") and v.datatype:
                reg_value["data_type"] = str(v.datatype)
            cybox_reg["values"].append(reg_value)
    return cybox_reg


def convert_process(process):
    cybox_p = {}
    if process.name:
        cybox_p["name"] = str(process.name)
    if process.pid:
        cybox_p["pid"] = str(process.pid)
    if process.creation_time:
        cybox_p["created"] = convert_timestamp(process.creation_time)
    if isinstance(process, WinProcess):
        extended_properties = {}
        process_properties = convert_windows_process(process)
        if process_properties:
            extended_properties["windows-process-ext"] = process_properties
        if isinstance(process, WinService):
            service_properties = convert_windows_service(process)
            if service_properties:
                extended_properties["windows-service-ext"] = service_properties
        if extended_properties:
            cybox_p["extended_properties"] = extended_properties
    if cybox:
        cybox_p["type"] = "process"
    return cybox_p


def convert_windows_process(process):
    ext = {}
    if process.handle_list:
        for h in process.handle_list:
            warn("Window handles are not a part of CybOX 3.0")
    if process.aslr_enabled:
        ext["asl_enabled"] = bool(process.aslr_enabled)
    if process.dep_enabled:
        ext["dep_enabled"] = bool(process.dep_enabled)
    if process.priority:
        ext["priority"] = str(process.priority)
    if process.security_type:
        ext["owner_sid"] = str(process.security_type)
    if process.window_title:
        ext["window_title"] = str(process.window_title)
    if process.startup_info:
        warn("process:startup_info not handled yet")
    return ext


def convert_windows_service(service):
    cybox_ws = {}
    if hasattr(service, "service_name") and service.service_name:
        cybox_ws["service_name"] = service.service_name.value
    if hasattr(service, "description_list") and service.description_list:
        descriptions = []
        for d in service.description_list:
            descriptions.append(d.value)
        cybox_ws["descriptions"] = descriptions
    if hasattr(service, "display_name") and service.display_name:
        cybox_ws["display_name"] = service.display_name.value
    if hasattr(service, "startup_command_line") and service.startup_command_line:
        cybox_ws["startup_command_line"] = service.startup_command_line.value
    if hasattr(service, "start_type") and service.start_type:
        cybox_ws["start_type"] = map_vocabs_to_label(service.start_type, SERVICE_START_TYPE)
    if hasattr(service, "service_type") and service.service_type:
        cybox_ws["service_type"] = map_vocabs_to_label(service.service_type, SERVICE_TYPE)
    if hasattr(service, "service_status") and service.service_status:
        cybox_ws["service_status"] = map_vocabs_to_label(service.service_status, SERVICE_STATUS)
    if hasattr(service, "service_dll") and service.service_dll:
        warn("WinServiceObject.service_dll is not handled, yet.")
    return cybox_ws


def convert_domain_name(domain_name):
    cybox_dm = {"type": "domain-name"}
    if domain_name.value:
        cybox_dm["value"] = domain_name.value

    # TODO: belongs_to_refs
    # TODO: description
    # TODO: extended_properties
    return cybox_dm


def convert_mutex(mutex):
    cybox_mutex = {"type": "mutex"}
    if mutex.name:
        cybox_mutex["name"] = mutex.name

    # TODO: description
    # TODO: extended_properties
    return cybox_mutex


def convert_network_connection(conn):
    # TODO: Implement when consensus on object is achieved.
    return {}


def convert_cybox_object(obj, cybox_container):
    prop = obj.properties
    if isinstance(prop, Address):
        cybox_obj = convert_address(prop)
    elif isinstance(prop, URI):
        cybox_obj = convert_uri(prop)
    elif isinstance(prop, File):
        cybox_obj = convert_file(prop)
    elif isinstance(prop, WinRegistryKey):
        cybox_obj = convert_registry_key(prop)
    elif isinstance(prop, Process):
        cybox_obj = convert_process(prop)
    elif isinstance(prop, DomainName):
        cybox_obj = convert_domain_name(prop)
    elif isinstance(prop, Mutex):
        cybox_obj = convert_mutex(prop)
    elif isinstance(prop, NetworkConnection):
        cybox_obj = convert_network_connection(prop)
    else:
        warn("{obj} not handled yet".format(obj=str(type(obj))))
        return None
    if cybox_obj:
        cybox_container["objects"] = {"0": cybox_obj}
        return cybox_container
    else:
        warn("{obj} didn't yield any STIX 2.0 object".format(obj=str(prop)))
        return None
