from oslo_config import cfg
import oslo_messaging as om
from pprint import pprint
import logging

import eventlet
eventlet.monkey_patch()


logging.basicConfig()
log = logging.getLogger()

log.addHandler(logging.StreamHandler())
log.setLevel(logging.INFO)


rabbit_group = cfg.OptGroup(name='oslo_messaging_rabbit',
                            title='RabbitMQ options')

opts = [
    cfg.StrOpt('rpc_backend'),
    cfg.StrOpt('rabbit_host'),
    cfg.PortOpt('rabbit_port'),
    cfg.StrOpt('rabbit_virtual_host'),
    cfg.StrOpt('rabbita_login_method'),
    cfg.StrOpt('rabbit_userid'),
    cfg.StrOpt('rabbit_password'),       
    ]
# 
#CONF = cfg.ConfigOpts()
CONF = cfg.CONF
CONF(['--config-file', 'rabbit.conf'])
#CONF.register_opts(opts)
CONF.register_opts(opts, group=rabbit_group) # or
#CONF.register_opts(opts, group='rabbit'))

# CONF.set_override('rpc_backend', 'rabbit')
# CONF.set_override('rabbit_host', '192.168.111.139')
# CONF.set_override('rabbit_port', 5672)
# CONF.set_override('rabbit_virtual_host', '/')
# CONF.set_override('rabbita_login_method', 'PLAIN')
# CONF.set_override('rabbit_userid', 'user1')
# CONF.set_override('rabbit_password', 'welcome123')
# 
# CONF.set_override('rpc_backend', 'rabbit', group='rabbit')
# CONF.set_override('rabbit_host', 'uvm3', group='rabbit')
# CONF.set_override('rabbit_port', 5672, group='rabbit')
# CONF.set_override('rabbit_virtual_host', '/', group='rabbit')
# CONF.set_override('rabbita_login_method', 'AMQPLAIN', group='rabbit')
# CONF.set_override('rabbit_userid', 'rabbit', group='rabbit')
# CONF.set_override('rabbit_password', 'welcome@123', group='rabbit')

# print(CONF.rabbit.rabbit_host)
print(CONF.oslo_messaging_rabbit.rabbit_host)
res = [{k:v} for k,v in cfg.CONF.items()]
pprint(res)


log.info('configuring connection')
#########RPC Server
# create transport and target
transport_url = 'rabbit://user1:welcome123@192.168.111.139:5672/'
transport = om.get_transport(CONF, transport_url)
#transport = om.get_rpc_transport(CONF)
'''
>>> dir(transport.conf)
['GroupAttrProxy', '__abstractmethods__', '__class__', '__contains__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattr__', '__getattribute__', '__getitem__', '__gt__', '__hash__', '__init__', '__iter__', '__le__', '__len__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__slots__', '__str__', '__subclasshook__', '__weakref__', '_abc_cache', '_abc_negative_cache', '_abc_negative_cache_version', '_abc_registry', '_conf', '_group', '_url', '_validate_query', 'get', 'items', 'keys', 'values']
>>> transport.conf.rabbit.get('rpc_backend', )
'rabbit'
>>> transport.conf.rabbit.get('rabbit_host', )
'uvm3'
'''
target = om.Target(topic = 'testme', server = '192.168.111.140')

# # create endpoints
class TestEndpoint(object):
    def test_method1(self, ctx, arg):
        return arg
endpoints = [TestEndpoint(),]
# 
# ## create sever
server = om.get_rpc_server(transport, target, endpoints, executor = 'eventlet')

'''
conf', 'decorate_ordered', 'dispatcher', 'executor_type', 'listener', 'reset', 'reset_states', 'start', 'stop', 'transport', 'wait']

>>> server.conf.rpc_backend
'rabbit'

>>> server.transport.conf.rabbit_host
'192.168.111.139'

'''
log.info('starting server')
server.start()


