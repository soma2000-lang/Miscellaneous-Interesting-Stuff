import sys
import pika
import time

def callback(ch, method, properties, body):
  print(" [X] Received %r" %body)
  time.sleep(body.count(b'.'))
  print('[x] Done')
  ch.basic_ack(delivery_tag = method.delivery_tag)
  

crdn = pika.PlainCredentials('rabbit', 'welcome@123')
connection = pika.BlockingConnection(pika.ConnectionParameters('uvm3', credentials=crdn))
chnnel = connection.channel()
chnnel.exchange_declare(exchange = 'log',
                        exchange_type = 'fanout')

result = chnnel.queue_declare(exclusive=True) #let the server choose a random queue name , and deleted 
#once the consumer connection is closed
queue_name = result.method.queue

chnnel.queue_bind(exchange='log',
                  queue = queue_name)
print(' [*] Waiting for logs. To exit press CTRL+C')


chnnel.basic_consume(callback,
                     queue= queue_name)

chnnel.start_consuming()