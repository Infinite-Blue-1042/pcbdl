# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS"BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Kicad Library part importer / exporter.
"""

__all__ = ["KicadPart", "read_kicad_netlist"]

from .base import Part, Pin, Net
from .context import *
from .small_parts import *

import re
import sexpdata

class PartNotFoundException(KeyError):
    pass

class _PowerSymbolException(Exception):
    pass

class KicadPart(Part):
    pass

REFDES_PREFIX_RE = re.compile("[^0-9]+") # Take only the prefix out of a full refdes
PIN_SPLITTER_RE = re.compile("[^\(\)/\s,]+") # Separate a kicad pin name into multiple pcbdl ones

# Improve a bit on sexpdata
def _better_Symbol_repr_(self):
    return f"s{self.value()!r}"
sexpdata.Symbol.__repr__=_better_Symbol_repr_

class _Better_sexp():
    @staticmethod
    def _process_item(item):
        if isinstance(item, list):
            return _Better_sexp(item)
        return item

    def __init__(self, input):
        self.l = [self._process_item(item) for item in input]

    def __getitem__(self, key):
        if isinstance(key, str):
            iterator = self.find_all_iter(key)
            try:
                ret = next(iterator)
            except StopIteration:
                raise KeyError(key)
            try:
                found_another = next(iterator)
            except StopIteration:
                pass
            else:
                raise KeyError(f"More than one {key!r}, expected only one.")
            return ret
        return self.l[key]

    def find_all_iter(self, key):
        for item in self.l:
            if not isinstance(item, _Better_sexp):
                continue
            if item[0].value() == key:
                yield item

    def find_all(self, key):
        return tuple(self.find_all_iter(key))

    def keys_iter(self):
        for item in self.l:
            if isinstance(item, _Better_sexp):
                yield item[0]
            else:
                yield item

    def keys(self):
        return list(self.keys_iter())

    def __repr__(self):
        return repr(self.l)

def _read_fields(part):
    return {f["name"][1]:f[2] for f in part["fields"][1:]}

def _read_properties(part):
    {p["name"][1]:p["value"][1] for p in part.find_all_iter("property")}

def read_kicad_netlist(filename):
    netlist_file = open(filename)
    netlist_contents = _Better_sexp(sexpdata.loads(netlist_file.read()))

    # Load part classes
    part_classes = [_read_kicad_netlist_partcls(part) for part in netlist_contents["libparts"][1:]]

    # Populate parts
    parts = {}
    for component in netlist_contents["components"][1:]:
        libsource = component["libsource"]
        lib = libsource["lib"][1]
        part_name = libsource["part"][1]

        for part_class in part_classes:
            if part_class._kicad_lib == lib and part_class._kicad_part == part_name:
                break
        else:
            raise PartNotFoundException(f"Can't find part {libsource[1:]} in the libparts loaded from the netlist.")

        part_instance = part_class(
            refdes=component["ref"][1],
            value=component["value"][1]
        )

        try:
            part_instance.package = component["footprint"][1]
        except KeyError:
            print(f"{part_instance} does not have a footprint defined.")

        part_instance.defined_at = filename # TODO: somehow add line numbers

        parts[part_instance.refdes] = part_instance

    # Instanciate nets and connect parts
    for net_sexp in netlist_contents["nets"][1:]:
        name = net_sexp["name"][1]
        nodes = net_sexp.find_all("node")

        if len(nodes) == 1 and name.startswith("Net-"):
            # we should just leave this NC, I think it's an autogenerated (by kicad) net that goes nowhere
            continue

        n = Net(name)
        n.defined_at = filename # TODO: somehow add line numbers

        for node in nodes:
            pin_number = node["pin"][1]
            part = parts[node["ref"][1]]

            for pin in part.pins:
                if pin_number in pin.numbers:
                    break
            else:
                raise KeyError(f"Couldn't find pin numbered {pin_number} on {part} as the netlist indicates.")

            if pin not in n.connections:
                # Kicad netlists are redundant, because they use physical pins listed
                # But we care about logical pins, so we have to make sure we didn't already connect this logical pin

                n << pin

    return parts, netlist_contents

def _read_kicad_netlist_partcls(libpart):
    lib = libpart["lib"][1]
    part_name = libpart["part"][1]
    description = libpart["description"][1]

    fields = _read_fields(libpart)
    pins = [{key:pin[key][1] for key in ["num", "name", "type"]} for pin in libpart["pins"][1:]]

    pcbdl_pins = []
    for pin in pins:
        if pin["name"] == "~":
                pin["name"] = "P%s"% pin["num"]
        pin_names = tuple(PIN_SPLITTER_RE.findall(pin["name"]))
        pin_numbers = tuple(PIN_SPLITTER_RE.findall(pin["num"]))
        pcbdl_pin = Pin(pin_numbers, pin_names)
        pcbdl_pin._kicad_pin = pin
        pcbdl_pins.append(pcbdl_pin)

    refdes_prefix = fields.pop("Reference", KicadPart.REFDES_PREFIX)

    class_dict = {
        "REFDES_PREFIX": refdes_prefix,
        "value": fields.pop("Value", ""),
        "package": fields.pop("Footprint", ""),
        "PINS": pcbdl_pins,
        #"fields": fields, # TODO: insert this when ready
    }

    class_dict["__doc__"] = (description + "\n\n" +
                             '\n'.join((f"{k}: {v}" for k, v in fields.items())))

    class_dict["_kicad_source_structure"] = libpart
    class_dict["_kicad_part"] = part_name
    class_dict["_kicad_lib"] = lib
    class_dict["_kicad_description"] = description

    parent_classes = (KicadPart,)
    if len(pcbdl_pins) == 2:
        if refdes_prefix == "R":
            parent_classes += (R,)
        if refdes_prefix == "C":
            parent_classes += (C,)

    return type(part_name, parent_classes, class_dict)
