#!/usr/bin/env python
import pika
import sys

crdn = pika.PlainCredentials('user1', 'welcome123')
connection = pika.BlockingConnection(pika.ConnectionParameters('uvm3', credentials=crdn))
channel = connection.channel()

channel.exchange_declare(exchange='direct_logs',
                         exchange_type='direct')

severity = sys.argv[1] if len(sys.argv) > 2 else 'info'
message = ' '.join(sys.argv[2:]) or 'Hello World!'
channel.basic_publish(exchange='direct_logs',
                      routing_key=severity,
                      body=message)
print(" [x] Sent %r:%r" % (severity, message))
connection.close()


'''
root@ubuntu:/home/ubuntu#
root@ubuntu:/home/ubuntu# rabbitmqctl  add_user  user1 welcome123
Adding user "user1" ...
root@ubuntu:/home/ubuntu# rabbitmqctl set_permissions -p / user1  '.*' '.*' '.*'
Setting permissions for user "user1" in vhost "/" ...
root@ubuntu:/home/ubuntu# rabbitmqctl  set_user_tags   user1 administrator
Setting tags for user "user1" to [administrator] ...
root@ubuntu:/home/ubuntu#
'''