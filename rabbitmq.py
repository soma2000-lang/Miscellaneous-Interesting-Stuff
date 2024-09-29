import sys
import pika

crdn = pika.PlainCredentials('rabbit', 'welcome@123')
connection = pika.BlockingConnection(pika.ConnectionParameters('uvm3', credentials=crdn))
chnnel = connection.channel()
'''
When RabbitMQ quits or crashes it will forget the queues and messages
 unless you tell it not to. Two things are required to make sure that 
 messages aren't lost: we need to mark both the queue and messages as durable.
 1. durable queue
 2. publish with delivery mode 2
'''
chnnel.queue_declare(queue='hello')  # can't be changed once declared
chnnel.queue_declare(queue='task_queue', durable = True)

message = ' '.join(sys.argv[1:]) or 'Hello World!'
# make the messages persistent even after rabbitmq server restarts
chnnel.basic_publish(exchange='', routing_key='hello', body= message,
                     properties = pika.BasicProperties(delivery_mode = 2 ))
#stronger guarantee then you can use publisher confirms.

print('[x] Sent % r' % message)