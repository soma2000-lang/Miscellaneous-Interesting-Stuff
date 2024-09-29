import sys
import pika

crdn = pika.PlainCredentials('rabbit', 'welcome@123')
connection = pika.BlockingConnection(pika.ConnectionParameters('uvm3', credentials=crdn))
chnnel = connection.channel()
chnnel.exchange_declare(exchange = 'log',
                        exchange_type = 'fanout')

message = ' '.join(sys.argv[1:]) or 'Hello World!'

# make the messages persistent even after rabbitmq server restarts
chnnel.basic_publish(exchange='log',
                     routing_key='',
                     body= message,
                     properties = pika.BasicProperties(delivery_mode = 2 ))
#stronger guarantee then you can use publisher confirms.

print('[x] Sent % r' % message)