"""
Bond Graph Model base files.
"""

import logging

from collections import namedtuple

import sympy as sp
from .exceptions import *

logger = logging.getLogger(__name__)


class BondGraphBase:
    def __init__(self, name=None, parent=None,
                 ports=None, description=None, params=None, metaclass=None):
        """
        Base class definition for all bond graphs.

        Args:
            name: Assumed to be unique
            metadata (dict):
        """

        # TODO: This is a dirty hack
        # Job for meta classes maybe?
        if not metaclass:
            self.__metaclass = "BondGraph"
        else:
            self.__metaclass = metaclass
        if not name:
            self.name = f"{self.metaclass}" \
                        f"{self.__class__.instances}"
        else:
            self.name = name
        self.parent = parent

        self.description = description
        if ports:
            self._ports = {
                (int(p) if p.isnumeric() else p):v for p,v in ports.items()
            }
        else:
            self._ports = {}
        """ List of exposed Power ports"""

        """ Dictionary of internal parameter and their values. The key is 
        the internal parameter, the value may be an exposed control value,
        a function of time, or a constant."""
        self.view = None
    def __repr__(self):
        return f"{self.metaclass}: {self.name}"
    def __new__(cls, *args, **kwargs):
        if "instances" not in cls.__dict__:
            cls.instances = 1
        else:
            cls.instances += 1

        return object.__new__(cls)

    def __del__(self):
        self.instances -= 1

    @property
    def metaclass(self):
        return self.__metaclass

    # @property
    # def max_ports(self):
    #     raise NotImplementedError

    @property
    def constitutive_relations(self):
        raise NotImplementedError

    @property
    def uri(self):
        if not self.parent:
            return ""
        else:
            return f"{self.parent.uri}/{self.name}"

    @property
    def root(self):
        if not self.parent:
            return self
        else:
            return self.parent.root

    @property
    def basis_vectors(self):
        raise NotImplementedError

    def __hash__(self):
        return id(self)

    # def __eq__(self, other):
    #     return self.__dict__ == other.__dict__


Bond = namedtuple("Bond", ["tail", "head"])

class Port(object):
    def __init__(self, component, index):
        self.component = component
        self.index = index
        self.is_connected = False

    def __iter__(self):
        return iter((self.component, self.index))
    def __len__(self):
        return 2
    def __getitem__(self, item):
        if item == 0:
            return self.component
        elif item == 1:
            return self.index
        else:
            raise KeyError
    def __hash__(self):
        return id(self)

    def __repr__(self):
        return f"Port({self.component}, {self.index})"

    def __eq__(self, other):
        try:
            return ((self.component is other.component) and
                (self.index == other.index))
        except AttributeError:
            try:
                c,p = other
                return  c is self.component and p == self.index
            except AttributeError:
                pass
        return False

class FixedPort:
    """
    Args:
        ports
    """

    def __init__(self, ports):
        self._ports = {}

        for port, data in ports.items():
            port_data = data if data else {}
            self._ports.update({Port(self, int(port)): port_data})

    def get_port(self, port=None):

        # If no port is specified, and there is only one port, grab it.
        if not port and not isinstance(port, int) and len(self._ports) == 1:
            for p in self._ports:
                if not p.is_connected:
                    return p
        # If it's a port object, then grab it
        elif port in self._ports and not port.is_connected:
            return port

        elif isinstance(port, int):
            p, = (pp for pp in self._ports if pp.index == port and
                    not pp.is_connected)
            if p:
               return p
        raise InvalidPortException

    def _port_vectors(self):
        return {
            sp.symbols((f"e_{port.index}", f"f_{port.index}")): port
            for port in self._ports
        }

    @property
    def ports(self):
        return self._ports

class PortExpander(FixedPort):

    def __init__(self,ports, static_ports=None):
        if static_ports:
            super().__init__(static_ports)
        else:
            super().__init__({})

        self._templates = {PortTemplate(self, p, v) for p,v in ports.items()}

        if len(self._templates) == 1:
            self._default_template, = self._templates
        else:
            self._default_template = False
        self.max_index =len(static_ports) if static_ports else 0

    def get_port(self, port=None):

        if not port and not isinstance(port, int):
            # port is None, so lets try and make a new one
            try:
                return self._default_template.spawn()
            except AttributeError:
                raise InvalidPortException("You must specify a port")
        elif port in self._templates:
            # this is a template, so lets
            template, = {t for t in self._templates if t == port}
            return template.spawn()

        elif isinstance(port, str):
            template, = {t for t in self._templates if t.index==port}
            return template.spawn()

        elif isinstance(port, int) and port\
                not in [p.index for p in self._ports]:
            try:
                return self._default_template.spawn(port)
            except AttributeError:
                raise InvalidPortException("You must specify a port")
        try: # suppose we've got port or a port tuple that exists
            return super().get_port(port)
        except InvalidPortException as ex:
            pass

        raise InvalidPortException(f"Could not create new port:{port}")

    def _port_vectors(self):
        return {
            sp.symbols((f"e_{port.index}", f"f_{port.index}")): port
            for port in self._ports if port.is_connected
        }

class PortTemplate(object):
    def __new__(cls, parent,index, data=None):
        self = object.__new__(cls)
        self.parent = parent
        self.index = index
        self.ports = []
        self.data = data if data else {}
        return self

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        try:
            p, s = other
            if p == self.parent and s == self.index:
                return True
        except TypeError:
            if other is self:
                return True
        return False

    def spawn(self, index=None):
        if not index:
            index = self.parent.max_index
        elif index in [p.index for p in self.parent.ports]:
            raise InvalidPortException("Could not create port: index "
                                       "already exists")
        port = Port(self.parent, index)
        port.__dict__.update({k:v for k,v in self.data.items()})
        self.parent._ports[port] = {}
        self.ports.append(port)
        self.parent.max_index = max(index, self.parent.max_index) + 1
        return port

