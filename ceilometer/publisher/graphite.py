# -*- encoding: utf-8 -*-
#
# Copyright 2014 Sashi Dahal, Robert van Leeuwen
#
# Author: Sashi Dahal <shashi.dahal@spilgames.com>
# Author: Robert van Leeuwen <robert.vanleeuwen@spilgames.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Publish to Graphite
"""

from ceilometer import publisher
from ceilometer.openstack.common import log
try:
    from oslo.utils import netutils as network_utils
except ImportError:
    from ceilometer.openstack.common import network_utils

try:
    from ceilometer.openstack.common.gettextutils import _
except ImportError:
    from ceilometer.i18n import _

import socket
from oslo.config import cfg
from oslo.config import types

import time
import re

PortType = types.Integer(1, 65535)

cfg.CONF.import_opt('udp_port', 'ceilometer.collector',
                    group='collector')


OPTS = [cfg.Opt('default_port',
                default=2003,
                type=PortType,
                help='Default port for communicating with Graphite'),
        cfg.StrOpt('protocol',
                   default='udp',
                   help='Protocol (tcp or udp) to use for '
                   'communicating with Graphite'),
        cfg.StrOpt('prefix',
                   default='ceilometer',
                   help='Graphite prefix key'),
        cfg.BoolOpt('hypervisor_in_prefix',
                    default=True,
                    help='If the hypervisor should be added to the prefix'),
        ]

cfg.CONF.register_opts(OPTS, group="graphite")

LOG = log.getLogger(__name__)


class GraphitePublisher(publisher.PublisherBase):

    def __init__(self, parsed_url):
        self.host, self.port = network_utils.parse_host_port(
            parsed_url.netloc,
            default_port=cfg.CONF.graphite.default_port)

        if cfg.CONF.graphite.hypervisor_in_prefix:
            self.prefix = (
                cfg.CONF.graphite.prefix
                + socket.gethostname().split('.')[0] + ".")
        else:
            self.prefix = cfg.CONF.graphite.prefix

    def graphitePush(self, metric):
        LOG.debug("Sending graphite metric:" + metric)

        if cfg.CONF.graphite.protocol.lower() == 'tcp':
            graphiteSock = socket.socket(socket.AF_INET,
                                         socket.SOCK_STREAM)
        elif cfg.CONF.graphite.protocol.lower() == 'udp':
            graphiteSock = socket.socket(socket.AF_INET,
                                         socket.SOCK_DGRAM)
        else:
            raise ValueError('%s: invalid protocol' % (
                cfg.CONF.graphite.protocol))

        graphiteSock.connect((self.host, self.port))
        graphiteSock.sendall(metric)
        graphiteSock.close()

    def publish_samples(self, context, samples):
        for sample in samples:

            stats_time = time.time()

            msg = sample.as_dict()
            prefix = self.prefix
            # for getting a clear idea of the attributes
            resource_id = msg['resource_id']
            project_id = msg['project_id']
            data_type = msg['type']  # gauge, cumulative, delta
            volume = msg['volume']  # usage
            metric_name = msg['name'].replace('.','_')  # network,instance,cpu, disk etc ..
            metadata = msg['resource_metadata']
            project_name = msg['project_name'].replace('.','_')
            instance_name = metadata['display_name'].replace('.','_') + '_' +resource_id[0:6]

            instance_match = re.match('instance', metric_name)


            if data_type == 'gauge' and instance_match is None:
                try:
                    data_to_send = "{}{}.{}.{} {} {}\n".format(prefix, project_name, instance_name, metric_name, volume, stats_time)
                    self.graphitePush(data_to_send)

                except Exception as e:
                    LOG.warn(_("Unable to send to Graphite"))
                    LOG.exception(e)

    def publish_events(self, context, events):
        """Send an event message for publishing

        :param context: Execution context from the service or RPC call
        :param events: events from pipeline after transformation
        """
        raise ceilometer.NotImplementedError
