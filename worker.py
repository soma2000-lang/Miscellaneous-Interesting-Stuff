import pika
import time

def callback(ch, method, properties, body):
  print(" [X] Received %r" %body)
  time.sleep(body.count(b'.'))
  print('[x] Done')
  ch.basic_ack(delivery_tag = method.delivery_tag)
  
'''
It's a common mistake to miss the basic_ack. It's an easy error, 
but the consequences are serious. Messages will be redelivered 
when your client quits (which may look like random redelivery), 
but RabbitMQ will eat more and more memory as it won't be able to
release any unacked messages.
In order to debug this kind of mistake you can use rabbitmqctl to
 print the messages_unacknowledged field:
'''

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
'''don't dispatch a new message to a worker until it has processed 
and acknowledged the previous one. Instead, it will dispatch it to 
the next worker that is not still busy.
'''
chnnel.basic_qos(prefetch_count=1)

#chnnel.basic_consume(callback, queue='hello', no_ack=True)
# re-deliver the message even when the consumer dies
chnnel.basic_consume(callback, queue='hello')
chnnel.start_consuming()